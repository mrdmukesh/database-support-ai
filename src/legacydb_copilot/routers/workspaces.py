from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.db.models import WorkspaceModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.schemas import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate

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
    return list(
        db.query(WorkspaceModel)
        .filter(WorkspaceModel.organization_id == organization_id)
        .order_by(WorkspaceModel.name)
        .all()
    )


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
    assert_same_organization(current_user, workspace.organization_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(workspace, field, value)
    try:
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
    assert_same_organization(current_user, workspace.organization_id)
    workspace.is_active = False
    db.commit()
