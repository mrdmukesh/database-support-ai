from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.config import Settings
from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.db.models import WorkspaceMembershipModel, WorkspaceModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.schemas import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from legacydb_copilot.security.access_control import (
    WorkspaceRole,
    ensure_workspace_membership,
    require_workspace_access,
)
from legacydb_copilot.services.audit_service import record_audit_event

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("workspaces:manage")),
) -> WorkspaceModel:
    assert_same_organization(current_user, payload.organization_id)
    workspace = WorkspaceModel(
        organization_id=payload.organization_id,
        name=payload.name,
        slug=payload.slug,
    )
    db.add(workspace)
    try:
        db.flush()
        ensure_workspace_membership(
            db,
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceRole.OWNER,
        )
        record_audit_event(
            db,
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            user_id=current_user.id,
            action="workspace.create",
            resource_type="workspace",
            resource_id=workspace.id,
            metadata={"name": workspace.name, "slug": workspace.slug},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Workspace already exists or org is invalid") from exc
    db.refresh(workspace)
    return workspace


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(
    organization_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("workspaces:read")),
) -> list[WorkspaceModel]:
    assert_same_organization(current_user, organization_id)
    query = db.query(WorkspaceModel).filter(WorkspaceModel.organization_id == organization_id)
    if Settings.from_env().feature_enterprise_rbac_enabled:
        workspace_ids = [
            item.workspace_id
            for item in db.query(WorkspaceMembershipModel.workspace_id)
            .filter(
                WorkspaceMembershipModel.user_id == current_user.id,
                WorkspaceMembershipModel.is_active.is_(True),
            )
            .all()
        ]
        query = query.filter(WorkspaceModel.id.in_(workspace_ids or [""]))
    return list(query.order_by(WorkspaceModel.name).all())


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("workspaces:manage")),
) -> WorkspaceModel:
    workspace = db.get(WorkspaceModel, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    require_workspace_access(db, current_user, workspace.id, action="manage")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(workspace, field, value)
    try:
        record_audit_event(
            db,
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            user_id=current_user.id,
            action="workspace.update",
            resource_type="workspace",
            resource_id=workspace.id,
            metadata={"fields": sorted(data.keys())},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Workspace could not be updated") from exc
    db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("workspaces:manage")),
) -> None:
    workspace = db.get(WorkspaceModel, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    require_workspace_access(db, current_user, workspace.id, action="manage")
    workspace.is_active = False
    record_audit_event(
        db,
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
        action="workspace.delete",
        resource_type="workspace",
        resource_id=workspace.id,
    )
    db.commit()
