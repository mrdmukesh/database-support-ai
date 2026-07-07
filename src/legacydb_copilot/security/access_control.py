from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role
from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import UserModel, WorkspaceMembershipModel, WorkspaceModel


class WorkspaceRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    DBA = "DBA"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"
    AUDITOR = "AUDITOR"


_MANAGE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}
_DATABASE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.DBA}
_WRITE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.DBA, WorkspaceRole.DEVELOPER}
_READ_ROLES = {
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.DBA,
    WorkspaceRole.DEVELOPER,
    WorkspaceRole.VIEWER,
    WorkspaceRole.AUDITOR,
}


def require_workspace_access(
    db: Session,
    current_user: UserModel,
    workspace_id: str,
    *,
    action: str = "read",
) -> WorkspaceModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Centralizes workspace membership and role validation for API requests.

    Input:
        Current authenticated user, workspace id, app database session, and requested action.

    Output:
        WorkspaceModel when access is allowed; raises HTTP 403/404 when denied.

    Called by:
        Workspace, database connection, document, investigation, report, verification, and learning-loop endpoints.

    Flow:
        Authenticated request -> Workspace Access Control -> route-specific business action.

    Safety:
        Enforces tenant/workspace isolation when enterprise RBAC is enabled while preserving legacy behavior when
        the feature flag is disabled.
    """

    workspace = db.get(WorkspaceModel, workspace_id)
    if workspace is None or not workspace.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    require_resource_workspace_access(
        db,
        current_user,
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        action=action,
    )
    return workspace


def require_resource_workspace_access(
    db: Session,
    current_user: UserModel,
    *,
    organization_id: str,
    workspace_id: str,
    action: str = "read",
) -> None:
    if current_user.organization_id != organization_id and current_user.role != Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied")
    if not Settings.from_env().feature_enterprise_rbac_enabled:
        return
    if current_user.role == Role.SUPER_ADMIN.value:
        return
    membership = _membership(db, current_user.id, workspace_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied")
    role = WorkspaceRole(membership.role)
    if not _role_allows(role, action):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace action denied")


def ensure_workspace_membership(
    db: Session,
    *,
    organization_id: str,
    workspace_id: str,
    user_id: str,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> WorkspaceMembershipModel:
    existing = _membership(db, user_id, workspace_id)
    if existing is not None:
        return existing
    membership = WorkspaceMembershipModel(
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        role=role.value,
        is_active=True,
    )
    db.add(membership)
    return membership


def require_resource_owner_workspace(
    db: Session,
    current_user: UserModel,
    resource: Any,
    *,
    action: str = "read",
) -> None:
    require_resource_workspace_access(
        db,
        current_user,
        organization_id=resource.organization_id,
        workspace_id=resource.workspace_id,
        action=action,
    )


def _membership(db: Session, user_id: str, workspace_id: str) -> WorkspaceMembershipModel | None:
    return (
        db.query(WorkspaceMembershipModel)
        .filter(
            WorkspaceMembershipModel.user_id == user_id,
            WorkspaceMembershipModel.workspace_id == workspace_id,
            WorkspaceMembershipModel.is_active.is_(True),
        )
        .first()
    )


def _role_allows(role: WorkspaceRole, action: str) -> bool:
    if action in {"manage", "admin"}:
        return role in _MANAGE_ROLES
    if action in {"database", "verify"}:
        return role in _DATABASE_ROLES
    if action in {"write", "investigate", "upload", "approve"}:
        return role in _WRITE_ROLES
    return role in _READ_ROLES
