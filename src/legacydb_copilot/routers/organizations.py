from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.db.models import OrganizationModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.schemas import OrganizationCreate, OrganizationRead

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> OrganizationModel:
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
def list_organizations(db: Annotated[Session, Depends(get_db_session)]) -> list[OrganizationModel]:
    return list(db.query(OrganizationModel).order_by(OrganizationModel.name).all())
