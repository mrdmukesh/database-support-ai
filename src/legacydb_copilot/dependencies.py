from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role, has_permission
from legacydb_copilot.common import DomainError
from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import UserModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db_session)],
) -> UserModel:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    try:
        payload = decode_access_token(credentials.credentials, secret=Settings.from_env().jwt_secret)
    except DomainError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = db.get(UserModel, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not active")
    if user.organization_id != payload.get("organization_id") or user.role != payload.get("role"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token claims are stale")
    return user


def require_permission(permission: str) -> Callable[[UserModel], UserModel]:
    def dependency(current_user: Annotated[UserModel, Depends(get_current_user)]) -> UserModel:
        try:
            role = Role(current_user.role)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown role") from exc
        if not has_permission(role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return current_user

    return dependency


def assert_same_organization(current_user: UserModel, organization_id: str) -> None:
    if current_user.organization_id != organization_id and current_user.role != Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied")


def assert_same_user(current_user: UserModel, user_id: str) -> None:
    if current_user.id != user_id and current_user.role != Role.SUPER_ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User scope denied")
