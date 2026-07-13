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
