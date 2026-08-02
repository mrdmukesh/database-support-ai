from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role
from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import (
    LLMModelCatalogModel,
    LLMModelPolicyModel,
    LLMModelRoleEntitlementModel,
    LLMModelSelectionAuditModel,
    LLMModelUserEntitlementModel,
    LLMModelWorkspaceEntitlementModel,
    UserModel,
)
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import (
    assert_same_organization,
    get_current_user,
    require_permission,
)
from legacydb_copilot.schemas import (
    ModelCatalogCreate,
    ModelCatalogRead,
    ModelCatalogUpdate,
    ModelEntitlementUpdate,
    ModelPolicyUpdate,
    UserModelAccessUpdate,
)
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.governed_model_selection import GovernedModelSelectionService

router = APIRouter(prefix="/models", tags=["models"])
admin_router = APIRouter(prefix="/admin", tags=["model-management"])
AdminUser = Annotated[UserModel, Depends(require_permission("models:manage"))]


def _admin_enabled() -> None:
    if not Settings.from_env().model_selection_admin_enabled:
        raise HTTPException(status_code=404, detail="Model management is disabled.")


def _policy_dict(policy: LLMModelPolicyModel | None) -> dict:
    if policy is None:
        return {
            "id": "",
            "organization_id": "",
            "user_selection_enabled": False,
            "automatic_mode_enabled": False,
            "admin_management_enabled": True,
            "global_default_model_id": None,
            "automatic_candidate_ids": [],
            "fallback_model_id": None,
            "fallback_enabled": False,
            "require_premium_approval": True,
            "allowed_environments": [],
            "selection_roles": [],
            "cost_ceiling_tier": "premium",
            "latency_preference": "balanced",
            "configuration_version": 0,
        }
    return {
        "id": policy.id,
        "organization_id": policy.organization_id,
        "user_selection_enabled": policy.user_selection_enabled,
        "automatic_mode_enabled": policy.automatic_mode_enabled,
        "admin_management_enabled": policy.admin_management_enabled,
        "global_default_model_id": policy.global_default_model_id,
        "automatic_candidate_ids": json.loads(policy.automatic_candidate_ids_json or "[]"),
        "fallback_model_id": policy.fallback_model_id,
        "fallback_enabled": policy.fallback_enabled,
        "require_premium_approval": policy.require_premium_approval,
        "allowed_environments": json.loads(policy.allowed_environments_json or "[]"),
        "selection_roles": json.loads(policy.selection_roles_json or "[]"),
        "cost_ceiling_tier": policy.cost_ceiling_tier,
        "latency_preference": policy.latency_preference,
        "configuration_version": policy.configuration_version,
    }


@router.get("/available")
def available_models(
    workspace_id: str,
    environment: str = "development",
    db: Annotated[Session, Depends(get_db_session)] = None,
    current_user: Annotated[UserModel, Depends(get_current_user)] = None,
) -> dict:
    return GovernedModelSelectionService(db).available_response(
        user=current_user, workspace_id=workspace_id, environment=environment
    )


@router.get("/effective-policy")
def effective_policy(
    workspace_id: str,
    environment: str = "development",
    db: Annotated[Session, Depends(get_db_session)] = None,
    current_user: Annotated[UserModel, Depends(get_current_user)] = None,
) -> dict:
    response = GovernedModelSelectionService(db).available_response(
        user=current_user, workspace_id=workspace_id, environment=environment
    )
    return {
        "selection_enabled": response["selection_enabled"],
        "automatic_enabled": response["automatic_enabled"],
        "default_value": response["default_value"],
        "policy_version": response["policy_version"],
        "allowed_option_count": len(response["options"]),
    }


@admin_router.get("/models", response_model=list[ModelCatalogRead])
def list_catalog(
    organization_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> list[LLMModelCatalogModel]:
    _admin_enabled()
    assert_same_organization(current_user, organization_id)
    return (
        db.query(LLMModelCatalogModel)
        .filter_by(organization_id=organization_id)
        .order_by(LLMModelCatalogModel.sort_order, LLMModelCatalogModel.display_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


@admin_router.post("/models", response_model=ModelCatalogRead, status_code=status.HTTP_201_CREATED)
def create_catalog_model(
    payload: ModelCatalogCreate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
) -> LLMModelCatalogModel:
    _admin_enabled()
    assert_same_organization(current_user, payload.organization_id)
    row = LLMModelCatalogModel(**payload.model_dump())
    db.add(row)
    db.flush()
    record_audit_event(
        db,
        organization_id=payload.organization_id,
        user_id=current_user.id,
        action="model_catalog.create",
        resource_type="llm_model",
        resource_id=row.id,
        metadata={"display_name": row.display_name, "provider": row.provider},
    )
    db.commit()
    db.refresh(row)
    return row


@admin_router.patch("/models/{model_id}", response_model=ModelCatalogRead)
def update_catalog_model(
    model_id: str,
    payload: ModelCatalogUpdate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
) -> LLMModelCatalogModel:
    _admin_enabled()
    row = db.get(LLMModelCatalogModel, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Model not found")
    assert_same_organization(current_user, row.organization_id)
    changes = payload.model_dump(exclude_unset=True)
    old = {key: getattr(row, key) for key in changes}
    for key, value in changes.items():
        setattr(row, key, value)
    row.configuration_version += 1
    record_audit_event(
        db,
        organization_id=row.organization_id,
        user_id=current_user.id,
        action="model_catalog.update",
        resource_type="llm_model",
        resource_id=row.id,
        metadata={"old": old, "new": changes},
    )
    db.commit()
    db.refresh(row)
    return row


@admin_router.get("/model-policies")
def get_model_policy(
    organization_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
) -> dict:
    _admin_enabled()
    assert_same_organization(current_user, organization_id)
    return _policy_dict(GovernedModelSelectionService(db).policy_for(organization_id))


@admin_router.patch("/model-policies/{organization_id}")
def update_model_policy(
    organization_id: str,
    payload: ModelPolicyUpdate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
) -> dict:
    _admin_enabled()
    assert_same_organization(current_user, organization_id)
    policy = GovernedModelSelectionService(db).policy_for(organization_id)
    if policy is None:
        policy = LLMModelPolicyModel(organization_id=organization_id)
        db.add(policy)
        db.flush()
    old = _policy_dict(policy)
    changes = payload.model_dump(exclude_unset=True)
    json_fields = {
        "automatic_candidate_ids": "automatic_candidate_ids_json",
        "allowed_environments": "allowed_environments_json",
        "selection_roles": "selection_roles_json",
    }
    for key, value in changes.items():
        if key in json_fields:
            setattr(policy, json_fields[key], json.dumps(value or []))
        else:
            setattr(policy, key, value)
    policy.configuration_version += 1
    updated = _policy_dict(policy)
    record_audit_event(
        db,
        organization_id=organization_id,
        user_id=current_user.id,
        action="model_policy.update",
        resource_type="llm_model_policy",
        resource_id=policy.id,
        metadata={"old": old, "new": updated},
    )
    db.commit()
    return updated


def _effective_access(db: Session, target: UserModel, workspace_id: str, environment: str) -> dict:
    service = GovernedModelSelectionService(db)
    response = service.available_response(
        user=target, workspace_id=workspace_id, environment=environment
    )
    response["user_id"] = target.id
    response["role"] = target.role
    return response


@admin_router.get("/users/{user_id}/model-access")
def get_user_model_access(
    user_id: str,
    workspace_id: str,
    environment: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
) -> dict:
    _admin_enabled()
    target = db.get(UserModel, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    assert_same_organization(current_user, target.organization_id)
    return _effective_access(db, target, workspace_id, environment)


@admin_router.put("/users/{user_id}/model-access")
def put_user_model_access(
    user_id: str,
    payload: UserModelAccessUpdate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
) -> dict:
    _admin_enabled()
    target = db.get(UserModel, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    assert_same_organization(current_user, payload.organization_id)
    assert_same_organization(current_user, target.organization_id)
    for item in payload.entitlements:
        model = db.get(LLMModelCatalogModel, item.model_id)
        if model is None or model.organization_id != target.organization_id:
            raise HTTPException(status_code=422, detail="Unknown catalog model")
        row = (
            db.query(LLMModelUserEntitlementModel)
            .filter_by(
                organization_id=target.organization_id, model_id=item.model_id, user_id=target.id
            )
            .one_or_none()
        )
        if row is None:
            row = LLMModelUserEntitlementModel(
                organization_id=target.organization_id,
                model_id=item.model_id,
                user_id=target.id,
                approved_by_id=current_user.id,
            )
            db.add(row)
        row.allowed = item.allowed
        row.approval_starts_at = item.approval_starts_at
        row.approval_expires_at = item.approval_expires_at
        row.approved_by_id = current_user.id
    record_audit_event(
        db,
        organization_id=target.organization_id,
        user_id=current_user.id,
        action="model_access.user_update",
        resource_type="user",
        resource_id=target.id,
        metadata={"model_ids": [item.model_id for item in payload.entitlements]},
    )
    db.commit()
    return {"user_id": target.id, "updated": len(payload.entitlements)}


@admin_router.put("/model-roles/{role}/access")
def put_role_model_access(
    role: Role,
    organization_id: str,
    entitlements: list[ModelEntitlementUpdate],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
) -> dict:
    _admin_enabled()
    assert_same_organization(current_user, organization_id)
    for item in entitlements:
        row = (
            db.query(LLMModelRoleEntitlementModel)
            .filter_by(organization_id=organization_id, model_id=item.model_id, role=role.value)
            .one_or_none()
        )
        if row is None:
            row = LLMModelRoleEntitlementModel(
                organization_id=organization_id, model_id=item.model_id, role=role.value
            )
            db.add(row)
        row.allowed = item.allowed
    record_audit_event(
        db,
        organization_id=organization_id,
        user_id=current_user.id,
        action="model_access.role_update",
        resource_type="role",
        resource_id=role.value,
        metadata={"model_ids": [item.model_id for item in entitlements]},
    )
    db.commit()
    return {"role": role.value, "updated": len(entitlements)}


@admin_router.put("/model-workspaces/{workspace_id}/access")
def put_workspace_model_access(
    workspace_id: str,
    organization_id: str,
    entitlements: list[ModelEntitlementUpdate],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
) -> dict:
    _admin_enabled()
    assert_same_organization(current_user, organization_id)
    for item in entitlements:
        row = (
            db.query(LLMModelWorkspaceEntitlementModel)
            .filter_by(
                organization_id=organization_id, model_id=item.model_id, workspace_id=workspace_id
            )
            .one_or_none()
        )
        if row is None:
            row = LLMModelWorkspaceEntitlementModel(
                organization_id=organization_id, model_id=item.model_id, workspace_id=workspace_id
            )
            db.add(row)
        row.allowed = item.allowed
    db.commit()
    return {"workspace_id": workspace_id, "updated": len(entitlements)}


@admin_router.get("/model-selection-audit")
def model_selection_audit(
    organization_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    _admin_enabled()
    assert_same_organization(current_user, organization_id)
    query = db.query(LLMModelSelectionAuditModel).filter_by(organization_id=organization_id)
    total = query.count()
    rows = (
        query.order_by(LLMModelSelectionAuditModel.requested_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "workspace_id": row.workspace_id,
                "investigation_id": row.investigation_id,
                "requested_mode": row.requested_mode,
                "requested_catalog_model_id": row.requested_catalog_model_id,
                "effective_catalog_model_id": row.effective_catalog_model_id,
                "effective_provider": row.effective_provider,
                "effective_provider_model_id": row.effective_provider_model_id,
                "selection_source": row.selection_source,
                "policy_decision": row.policy_decision,
                "policy_decision_reason": row.policy_decision_reason,
                "entitlement_source": row.entitlement_source,
                "fallback_reason": row.fallback_reason,
                "requested_at": row.requested_at,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }
