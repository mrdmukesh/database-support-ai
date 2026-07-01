from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from legacydb_copilot.common import DomainError
from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.db.models import IncidentModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.incidents import Incident, IncidentStatus
from legacydb_copilot.schemas import IncidentCreate, IncidentRead, IncidentTransition

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("incidents:write")),
) -> IncidentModel:
    assert_same_organization(current_user, payload.organization_id)
    incident = IncidentModel(**payload.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.post("/{incident_id}/transition", response_model=IncidentRead)
def transition_incident(
    incident_id: str,
    payload: IncidentTransition,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("incidents:manage")),
) -> IncidentModel:
    incident_model = db.get(IncidentModel, incident_id)
    if incident_model is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    assert_same_organization(current_user, incident_model.organization_id)

    domain_incident = Incident(
        organization_id=incident_model.organization_id,  # type: ignore[arg-type]
        workspace_id=incident_model.workspace_id,  # type: ignore[arg-type]
        title=incident_model.title,
        created_by=incident_model.created_by_id,  # type: ignore[arg-type]
    )
    domain_incident.status = IncidentStatus(incident_model.status)
    try:
        domain_incident.transition(payload.status)
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    incident_model.status = domain_incident.status.value
    db.commit()
    db.refresh(incident_model)
    return incident_model
