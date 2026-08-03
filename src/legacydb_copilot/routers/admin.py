from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role, validate_password_strength
from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.db.models import (
    DocumentModel,
    IncidentModel,
    OrganizationModel,
    SubscriptionModel,
    UserModel,
)
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.schemas import AdminUserCreate, AdminUserUpdate, UserRead
from legacydb_copilot.security import hash_password
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import (
    DatabaseConnectionModel,
    InvestigationModel,
    InvestigationAgenticStepModel,
    InvestigationPlannerSelectionModel,
    ExecutionPathTraceModel,
    InvestigationFeedbackModel,
    VerificationCheckModel,
    WorkspaceModel,
    WorkspaceMembershipModel,
        AuditLogModel,
        LLMInvocationAuditModel,
)
from pydantic import BaseModel
import uuid
import os

router = APIRouter(prefix="/admin", tags=["admin"])


def _guard_role_assignment(current_user: UserModel, role: Role) -> None:
    if role == Role.SUPER_ADMIN and current_user.role != Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only a super administrator can assign this role")


@router.get("/users", response_model=list[UserRead])
def list_users(
    organization_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("users:manage")),
) -> list[UserModel]:
    assert_same_organization(current_user, organization_id)
    return list(db.query(UserModel).filter(UserModel.organization_id == organization_id).order_by(UserModel.full_name, UserModel.email).all())


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("users:manage")),
) -> UserModel:
    assert_same_organization(current_user, payload.organization_id)
    _guard_role_assignment(current_user, payload.role)
    errors = validate_password_strength(payload.password)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    user = UserModel(organization_id=payload.organization_id, email=payload.email.strip().lower(), password_hash=hash_password(payload.password), full_name=payload.full_name.strip(), role=payload.role.value, is_active=True)
    db.add(user)
    try:
        db.flush()
        record_audit_event(db, organization_id=user.organization_id, user_id=current_user.id, action="user.create", resource_type="user", resource_id=user.id, metadata={"role": user.role})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A user with this email already exists") from exc
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("users:manage")),
) -> UserModel:
    user = db.get(UserModel, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    assert_same_organization(current_user, user.organization_id)
    data = payload.model_dump(exclude_unset=True)
    if user.id == current_user.id and ("role" in data or data.get("is_active") is False):
        raise HTTPException(status_code=403, detail="You cannot change your own role or deactivate your account")
    if payload.role is not None:
        _guard_role_assignment(current_user, payload.role)
        if user.role == Role.SUPER_ADMIN.value and current_user.role != Role.SUPER_ADMIN.value:
            raise HTTPException(status_code=403, detail="Only a super administrator can modify this user")
        data["role"] = payload.role.value
    for field, value in data.items():
        setattr(user, field, value.strip() if field == "full_name" and value is not None else value)
    record_audit_event(db, organization_id=user.organization_id, user_id=current_user.id, action="user.update", resource_type="user", resource_id=user.id, metadata={"fields": sorted(data)})
    db.commit()
    db.refresh(user)
    return user


@router.get("/summary")
def admin_summary(
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("admin:read")),
) -> dict[str, int]:
    org_filter = True if current_user.role == Role.SUPER_ADMIN.value else (
        OrganizationModel.id == current_user.organization_id
    )
    active_subscriptions = db.query(func.count(SubscriptionModel.id)).filter(
        SubscriptionModel.active.is_(True),
        SubscriptionModel.organization_id == current_user.organization_id
        if current_user.role != Role.SUPER_ADMIN.value
        else True,
    ).scalar()
    return {
        "organizations": db.query(func.count(OrganizationModel.id)).filter(org_filter).scalar() or 0,
        "users": db.query(func.count(UserModel.id)).filter(
            UserModel.organization_id == current_user.organization_id
            if current_user.role != Role.SUPER_ADMIN.value
            else True
        ).scalar()
        or 0,
        "active_subscriptions": active_subscriptions or 0,
        "documents": db.query(func.count(DocumentModel.id)).filter(
            DocumentModel.organization_id == current_user.organization_id
            if current_user.role != Role.SUPER_ADMIN.value
            else True
        ).scalar()
        or 0,
        "incidents": db.query(func.count(IncidentModel.id)).filter(
            IncidentModel.organization_id == current_user.organization_id
            if current_user.role != Role.SUPER_ADMIN.value
            else True
        ).scalar()
        or 0,
    }


class CleanupConfirmation(BaseModel):
    confirmation: str
    keep_default_workspace: bool = True


@router.post("/test-data-cleanup/preview")
def preview_test_data_cleanup(
    organization_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("admin:read")),
) -> dict:
    """Return a dry-run summary of what would be deleted for the organization."""
    assert_same_organization(current_user, organization_id)
    settings = Settings.from_env()
    # Disallow in production
    if settings.environment.name.lower() == "production":
        raise HTTPException(status_code=403, detail="Cleanup is not allowed in production environment")

    counts = {}
    counts["connections"] = db.query(func.count(DatabaseConnectionModel.id)).filter(DatabaseConnectionModel.organization_id == organization_id).scalar() or 0
    counts["workspaces"] = db.query(func.count(WorkspaceModel.id)).filter(WorkspaceModel.organization_id == organization_id).scalar() or 0
    counts["workspace_memberships"] = db.query(func.count(WorkspaceMembershipModel.id)).filter(WorkspaceMembershipModel.organization_id == organization_id).scalar() or 0
    counts["investigations"] = db.query(func.count(InvestigationModel.id)).filter(InvestigationModel.organization_id == organization_id).scalar() or 0
    counts["agentic_steps"] = db.query(func.count(InvestigationAgenticStepModel.id)).filter(InvestigationAgenticStepModel.organization_id == organization_id).scalar() or 0
    counts["planner_selections"] = db.query(func.count(InvestigationPlannerSelectionModel.id)).filter(InvestigationPlannerSelectionModel.organization_id == organization_id).scalar() or 0
    counts["execution_traces"] = db.query(func.count(ExecutionPathTraceModel.id)).filter(ExecutionPathTraceModel.organization_id == organization_id).scalar() or 0
    counts["feedback"] = db.query(func.count(InvestigationFeedbackModel.id)).filter(InvestigationFeedbackModel.organization_id == organization_id).scalar() or 0
    counts["verification_checks"] = db.query(func.count(VerificationCheckModel.id)).filter(VerificationCheckModel.organization_id == organization_id).scalar() or 0

    # Determine dependency order (FK-safe)
    dependency_order = [
        "reports_and_metadata",
        "feedback",
        "evidence",
        "evidence_packages",
        "llm_invocation_audit",
        "prompt_audit",
        "execution_traces",
        "agentic_steps",
        "planner_selections",
        "verification_and_root_cause",
        "graph_checkpoints",
        "investigations",
        "connection_workspace_mappings",
        "connection_user_mappings",
        "stored_credentials",
        "database_connections",
        "workspace_memberships",
        "workspaces",
    ]

    shared = db.query(DatabaseConnectionModel.workspace_id).filter(DatabaseConnectionModel.organization_id == organization_id).distinct().all()
    shared_workspaces = [s[0] for s in shared if s[0]]

    return {
        "counts": counts,
        "dependency_order": dependency_order,
        "shared_workspace_ids_sample": shared_workspaces[:10],
        "zero_workspaces_supported": True,
        "one_default_workspace_required": False,
    }


@router.post("/test-data-cleanup/execute")
def execute_test_data_cleanup(
    organization_id: str,
    payload: CleanupConfirmation,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("admin:read")),
) -> dict:
    """Execute the destructive cleanup of test data for the organization.

    This endpoint is protected and requires explicit confirmation text and an environment guard.
    """
    assert_same_organization(current_user, organization_id)
    # Env guard
    if os.getenv("ALLOW_TEST_DATA_CLEANUP", "false").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Test data cleanup is disabled by environment")
    settings = Settings.from_env()
    if settings.environment.name.lower() == "production":
        raise HTTPException(status_code=403, detail="Cleanup is not allowed in production environment")
    if payload.confirmation != "DELETE TEST APP DATA":
        raise HTTPException(status_code=400, detail="Confirmation text mismatch")

    # perform transactional cleanup and gather detailed before counts
    before_counts = {}
    before_counts["connections"] = db.query(func.count(DatabaseConnectionModel.id)).filter(DatabaseConnectionModel.organization_id == organization_id).scalar() or 0
    before_counts["workspaces"] = db.query(func.count(WorkspaceModel.id)).filter(WorkspaceModel.organization_id == organization_id).scalar() or 0
    before_counts["investigations"] = db.query(func.count(InvestigationModel.id)).filter(InvestigationModel.organization_id == organization_id).scalar() or 0
    before_counts["evidence"] = db.query(func.count(DocumentModel.id)).filter(DocumentModel.organization_id == organization_id).scalar() or 0
    before_counts["reports"] = db.query(func.count(InvestigationModel.id)).filter(InvestigationModel.organization_id == organization_id, InvestigationModel.report_path != "").scalar() or 0
    before_counts["users"] = db.query(func.count(UserModel.id)).filter(UserModel.organization_id == organization_id).scalar() or 0

    # generate correlation id for structured audit logging
    correlation_id = str(uuid.uuid4())
    try:
        # Use nested transaction when a transaction is already active (test client / request lifecycle)
        tx = db.begin_nested() if db.in_transaction() else db.begin()
        with tx:
            # delete in FK-safe order using ORM model queries
            db.query(VerificationCheckModel).filter(VerificationCheckModel.organization_id == organization_id).delete(synchronize_session=False)
            db.query(InvestigationFeedbackModel).filter(InvestigationFeedbackModel.organization_id == organization_id).delete(synchronize_session=False)
            db.query(ExecutionPathTraceModel).filter(ExecutionPathTraceModel.organization_id == organization_id).delete(synchronize_session=False)
            db.query(InvestigationAgenticStepModel).filter(InvestigationAgenticStepModel.organization_id == organization_id).delete(synchronize_session=False)
            db.query(InvestigationPlannerSelectionModel).filter(InvestigationPlannerSelectionModel.organization_id == organization_id).delete(synchronize_session=False)
            # LLM invocation audit entries are stored without a FK to investigations; delete explicitly
            db.query(LLMInvocationAuditModel).filter(LLMInvocationAuditModel.organization_id == organization_id).delete(synchronize_session=False)
            db.query(InvestigationModel).filter(InvestigationModel.organization_id == organization_id).delete(synchronize_session=False)
            # stored credentials are in secret store; here we clear secret_ref values to empty string
            db.query(DatabaseConnectionModel).filter(DatabaseConnectionModel.organization_id == organization_id).update({DatabaseConnectionModel.secret_ref: ""}, synchronize_session=False)
            db.query(DatabaseConnectionModel).filter(DatabaseConnectionModel.organization_id == organization_id).delete(synchronize_session=False)
            db.query(WorkspaceMembershipModel).filter(WorkspaceMembershipModel.organization_id == organization_id).delete(synchronize_session=False)
            db.query(WorkspaceModel).filter(WorkspaceModel.organization_id == organization_id).delete(synchronize_session=False)

            # structured audit for start
            record_audit_event(
                db,
                organization_id=organization_id,
                user_id=current_user.id,
                action="admin.test_data_cleanup.start",
                resource_type="organization",
                resource_id=organization_id,
                metadata={"keeper_default_workspace": payload.keep_default_workspace, "correlation_id": correlation_id},
            )

    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {exc}") from exc

    # post-check: gather after counts
    after_counts = {}
    after_counts["connections"] = db.query(func.count(DatabaseConnectionModel.id)).filter(DatabaseConnectionModel.organization_id == organization_id).scalar() or 0
    after_counts["workspaces"] = db.query(func.count(WorkspaceModel.id)).filter(WorkspaceModel.organization_id == organization_id).scalar() or 0
    after_counts["investigations"] = db.query(func.count(InvestigationModel.id)).filter(InvestigationModel.organization_id == organization_id).scalar() or 0
    after_counts["evidence"] = db.query(func.count(DocumentModel.id)).filter(DocumentModel.organization_id == organization_id).scalar() or 0
    after_counts["reports"] = db.query(func.count(InvestigationModel.id)).filter(InvestigationModel.organization_id == organization_id, InvestigationModel.report_path != "").scalar() or 0
    after_counts["users"] = db.query(func.count(UserModel.id)).filter(UserModel.organization_id == organization_id).scalar() or 0

    if after_counts["workspaces"] == 0 and payload.keep_default_workspace:
        # create Default Workspace and membership
        ws = WorkspaceModel(organization_id=organization_id, name="Default Workspace", slug="default")
        db.add(ws)
        db.flush()
        membership = WorkspaceMembershipModel(organization_id=organization_id, workspace_id=ws.id, user_id=current_user.id, role="OWNER", is_active=True)
        db.add(membership)
        db.commit()
        after_counts["workspaces"] = 1

    # build summary
    summary = {
        "connections_deleted": max(0, before_counts.get("connections", 0) - after_counts.get("connections", 0)),
        "workspaces_deleted": max(0, before_counts.get("workspaces", 0) - after_counts.get("workspaces", 0)),
        "investigations_deleted": max(0, before_counts.get("investigations", 0) - after_counts.get("investigations", 0)),
        "evidence_deleted": max(0, before_counts.get("evidence", 0) - after_counts.get("evidence", 0)),
        "reports_deleted": max(0, before_counts.get("reports", 0) - after_counts.get("reports", 0)),
        "users_deleted": max(0, before_counts.get("users", 0) - after_counts.get("users", 0)),
        # physical DB deletions are not performed by this endpoint
        "physical_databases_deleted": 0,
    }

    # final audit log entry via record_audit_event (include correlation id)
    record_audit_event(
        db,
        organization_id=organization_id,
        user_id=current_user.id,
        action="admin.test_data_cleanup.final",
        resource_type="organization",
        resource_id=organization_id,
        metadata={"before": before_counts, "after": after_counts, "env": settings.environment.name, "correlation_id": correlation_id, "summary": summary},
    )

    return {"status": "ok", "before": before_counts, "after": after_counts, "summary": summary, "correlation_id": correlation_id}
