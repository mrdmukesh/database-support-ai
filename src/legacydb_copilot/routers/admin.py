from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role
from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.db.models import (
    DocumentModel,
    IncidentModel,
    OrganizationModel,
    SubscriptionModel,
    UserModel,
)
from legacydb_copilot.db.session import get_db_session

router = APIRouter(prefix="/admin", tags=["admin"])


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
