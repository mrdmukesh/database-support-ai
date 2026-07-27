from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from legacydb_copilot.db.models import InvestigationModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.schemas import (
    InvestigationStateHistoryRead,
    InvestigationStateTransitionRead,
)
from legacydb_copilot.security.access_control import require_resource_owner_workspace
from legacydb_copilot.services.investigation_state_machine import (
    InvestigationStateService,
    StateTransition,
)

router = APIRouter(prefix="/investigations", tags=["investigations"])


def _investigation(
    db: Session,
    investigation_id: str,
    current_user,
) -> InvestigationModel:
    investigation = db.get(InvestigationModel, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    require_resource_owner_workspace(db, current_user, investigation, action="read")
    return investigation


def _read(transition: StateTransition) -> InvestigationStateTransitionRead:
    return InvestigationStateTransitionRead(
        investigation_id=transition.investigation_id,
        previous_state=transition.previous_state.value if transition.previous_state else None,
        current_state=transition.current_state.value,
        transitioned_at=transition.transitioned_at,
        reason=transition.reason,
        iteration_number=transition.iteration_number,
    )


@router.get("/{investigation_id}/state", response_model=InvestigationStateTransitionRead)
def current_investigation_state(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> InvestigationStateTransitionRead:
    _investigation(db, investigation_id, current_user)
    current = InvestigationStateService(db).current(investigation_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Agentic state is not initialized")
    return _read(current)


@router.get(
    "/{investigation_id}/state/history",
    response_model=InvestigationStateHistoryRead,
)
def investigation_state_history(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> InvestigationStateHistoryRead:
    _investigation(db, investigation_id, current_user)
    transitions = InvestigationStateService(db).history(investigation_id)
    return InvestigationStateHistoryRead(
        investigation_id=investigation_id,
        current=_read(transitions[-1]) if transitions else None,
        transitions=[_read(item) for item in transitions],
    )
