from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role
from legacydb_copilot.common import DomainError
from legacydb_copilot.config import Settings
from legacydb_copilot.dependencies import bearer_scheme
from legacydb_copilot.db.models import UserModel
from legacydb_copilot.db.models import OrganizationModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.schemas import OrganizationCreate, OrganizationRead
from legacydb_copilot.security import decode_access_token

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _enterprise_current_user(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> UserModel | None:
    if not Settings.from_env().feature_enterprise_rbac_enabled:
        return None
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_access_token(credentials.credentials, secret=Settings.from_env().jwt_secret)
    except DomainError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = db.get(UserModel, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not active")
    if user.role != payload.get("role") or user.organization_id != payload.get("organization_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token claims are stale")
    return user


def _require_super_admin(user: UserModel | None) -> None:
    if Settings.from_env().feature_enterprise_rbac_enabled and (user is None or user.role != Role.SUPER_ADMIN.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Annotated[Session, Depends(get_db_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> OrganizationModel:
    _require_super_admin(_enterprise_current_user(credentials, db))
    organization = OrganizationModel(name=payload.name, slug=payload.slug)
    db.add(organization)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Organization already exists") from exc
    db.refresh(organization)
    return organization


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    db: Annotated[Session, Depends(get_db_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> list[OrganizationModel]:
    user = _enterprise_current_user(credentials, db)
    query = db.query(OrganizationModel)
    if Settings.from_env().feature_enterprise_rbac_enabled:
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        if user.role != Role.SUPER_ADMIN.value:
            query = query.filter(OrganizationModel.id == user.organization_id)
    return list(query.order_by(OrganizationModel.name).all())
