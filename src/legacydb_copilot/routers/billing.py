from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.db.models import SubscriptionModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.schemas import SubscriptionRead, SubscriptionUpsert

router = APIRouter(prefix="/billing", tags=["billing"])


@router.put("/subscription", response_model=SubscriptionRead)
def upsert_subscription(
    payload: SubscriptionUpsert,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("billing:manage")),
) -> SubscriptionModel:
    assert_same_organization(current_user, payload.organization_id)
    subscription = (
        db.query(SubscriptionModel)
        .filter(SubscriptionModel.organization_id == payload.organization_id)
        .one_or_none()
    )
    if subscription is None:
        subscription = SubscriptionModel(**payload.model_dump(mode="json"))
        db.add(subscription)
    else:
        for key, value in payload.model_dump(mode="json").items():
            setattr(subscription, key, value)
    db.commit()
    db.refresh(subscription)
    return subscription
