from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import utc_now
from legacydb_copilot.db.models import (
    InvestigationModel,
    InvestigationStateTransitionModel,
)
from legacydb_copilot.services.audit_service import record_audit_event


class InvestigationState(StrEnum):
    INITIALIZATION = "INITIALIZATION"
    EVIDENCE_ASSESSMENT = "EVIDENCE_ASSESSMENT"
    GAP_IDENTIFICATION = "GAP_IDENTIFICATION"
    ACTION_SELECTION = "ACTION_SELECTION"
    PLANNING = "PLANNING"
    VALIDATION = "VALIDATION"
    EXECUTION = "EXECUTION"
    VERIFICATION = "VERIFICATION"
    STATE_UPDATE = "STATE_UPDATE"
    STOP_EVALUATION = "STOP_EVALUATION"
    ROOT_CAUSE_CONFIRMED = "ROOT_CAUSE_CONFIRMED"
    ISSUE_NOT_REPRODUCED = "ISSUE_NOT_REPRODUCED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED_BY_MISSING_SOURCE = "BLOCKED_BY_MISSING_SOURCE"
    QUERY_BUDGET_EXHAUSTED = "QUERY_BUDGET_EXHAUSTED"
    ITERATION_BUDGET_EXHAUSTED = "ITERATION_BUDGET_EXHAUSTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = frozenset({
    InvestigationState.ROOT_CAUSE_CONFIRMED,
    InvestigationState.ISSUE_NOT_REPRODUCED,
    InvestigationState.INSUFFICIENT_EVIDENCE,
    InvestigationState.BLOCKED_BY_MISSING_SOURCE,
    InvestigationState.QUERY_BUDGET_EXHAUSTED,
    InvestigationState.ITERATION_BUDGET_EXHAUSTED,
    InvestigationState.POLICY_BLOCKED,
    InvestigationState.FAILED,
    InvestigationState.CANCELLED,
})

_FAIL_OR_CANCEL = frozenset({InvestigationState.FAILED, InvestigationState.CANCELLED})
ALLOWED_TRANSITIONS: dict[InvestigationState, frozenset[InvestigationState]] = {
    InvestigationState.INITIALIZATION: frozenset({
        InvestigationState.EVIDENCE_ASSESSMENT,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.EVIDENCE_ASSESSMENT: frozenset({
        InvestigationState.GAP_IDENTIFICATION,
        InvestigationState.ROOT_CAUSE_CONFIRMED,
        InvestigationState.ISSUE_NOT_REPRODUCED,
        InvestigationState.INSUFFICIENT_EVIDENCE,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.GAP_IDENTIFICATION: frozenset({
        InvestigationState.ACTION_SELECTION,
        InvestigationState.BLOCKED_BY_MISSING_SOURCE,
        InvestigationState.INSUFFICIENT_EVIDENCE,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.ACTION_SELECTION: frozenset({
        InvestigationState.PLANNING,
        InvestigationState.QUERY_BUDGET_EXHAUSTED,
        InvestigationState.ITERATION_BUDGET_EXHAUSTED,
        InvestigationState.POLICY_BLOCKED,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.PLANNING: frozenset({
        InvestigationState.VALIDATION,
        InvestigationState.POLICY_BLOCKED,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.VALIDATION: frozenset({
        InvestigationState.EXECUTION,
        InvestigationState.POLICY_BLOCKED,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.EXECUTION: frozenset({
        InvestigationState.VERIFICATION,
        InvestigationState.QUERY_BUDGET_EXHAUSTED,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.VERIFICATION: frozenset({
        InvestigationState.STATE_UPDATE,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.STATE_UPDATE: frozenset({
        InvestigationState.STOP_EVALUATION,
        *_FAIL_OR_CANCEL,
    }),
    InvestigationState.STOP_EVALUATION: frozenset({
        InvestigationState.EVIDENCE_ASSESSMENT,
        *TERMINAL_STATES,
    }),
}


class InvalidInvestigationTransition(ValueError):
    pass


class TerminalInvestigationState(RuntimeError):
    pass


@dataclass(frozen=True)
class StateTransition:
    investigation_id: str
    previous_state: InvestigationState | None
    current_state: InvestigationState
    transitioned_at: datetime
    reason: str
    iteration_number: int


def validate_transition(
    previous_state: InvestigationState,
    next_state: InvestigationState,
) -> None:
    if previous_state in TERMINAL_STATES:
        raise TerminalInvestigationState(
            f"Terminal state {previous_state.value} cannot execute another step"
        )
    if next_state not in ALLOWED_TRANSITIONS.get(previous_state, frozenset()):
        raise InvalidInvestigationTransition(
            f"Invalid investigation transition: {previous_state.value} -> {next_state.value}"
        )


class InvestigationStateService:
    def __init__(self, db: Session):
        self.db = db

    def initialize(
        self,
        investigation: InvestigationModel,
        *,
        reason: str = "Agentic state tracking initialized.",
    ) -> StateTransition:
        existing = self.current(investigation.id)
        if existing is not None:
            return existing
        return self._persist(
            investigation,
            previous_state=None,
            current_state=InvestigationState.INITIALIZATION,
            reason=reason,
            iteration_number=0,
        )

    def transition(
        self,
        investigation: InvestigationModel,
        next_state: InvestigationState,
        *,
        reason: str,
    ) -> StateTransition:
        current = self.current(investigation.id)
        if current is None:
            raise InvalidInvestigationTransition("Investigation state is not initialized")
        validate_transition(current.current_state, next_state)
        iteration = current.iteration_number
        if (
            current.current_state is InvestigationState.STOP_EVALUATION
            and next_state is InvestigationState.EVIDENCE_ASSESSMENT
        ):
            iteration += 1
        return self._persist(
            investigation,
            previous_state=current.current_state,
            current_state=next_state,
            reason=reason,
            iteration_number=iteration,
        )

    def cancel(self, investigation: InvestigationModel, *, reason: str) -> StateTransition:
        return self.transition(investigation, InvestigationState.CANCELLED, reason=reason)

    def fail(self, investigation: InvestigationModel, *, reason: str) -> StateTransition:
        return self.transition(investigation, InvestigationState.FAILED, reason=reason)

    def current(self, investigation_id: str) -> StateTransition | None:
        row = self.db.scalars(
            select(InvestigationStateTransitionModel)
            .where(InvestigationStateTransitionModel.investigation_id == investigation_id)
            .order_by(
                InvestigationStateTransitionModel.transitioned_at.desc(),
                InvestigationStateTransitionModel.id.desc(),
            )
            .limit(1)
        ).first()
        return _to_transition(row) if row else None

    def history(self, investigation_id: str) -> list[StateTransition]:
        rows = self.db.scalars(
            select(InvestigationStateTransitionModel)
            .where(InvestigationStateTransitionModel.investigation_id == investigation_id)
            .order_by(
                InvestigationStateTransitionModel.transitioned_at.asc(),
                InvestigationStateTransitionModel.id.asc(),
            )
        ).all()
        return [_to_transition(row) for row in rows]

    def _persist(
        self,
        investigation: InvestigationModel,
        *,
        previous_state: InvestigationState | None,
        current_state: InvestigationState,
        reason: str,
        iteration_number: int,
    ) -> StateTransition:
        timestamp = utc_now()
        row = InvestigationStateTransitionModel(
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            investigation_id=investigation.id,
            previous_state=previous_state.value if previous_state else "",
            current_state=current_state.value,
            transitioned_at=timestamp,
            reason=reason.strip(),
            iteration_number=iteration_number,
        )
        self.db.add(row)
        self.db.flush()
        record_audit_event(
            self.db,
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            user_id=investigation.created_by_id,
            action="INVESTIGATION_STATE_TRANSITIONED",
            resource_type="investigation",
            resource_id=investigation.id,
            metadata={
                "previous_state": previous_state.value if previous_state else None,
                "current_state": current_state.value,
                "iteration_number": iteration_number,
                "reason": reason.strip(),
            },
        )
        return _to_transition(row)


def _to_transition(row: InvestigationStateTransitionModel) -> StateTransition:
    return StateTransition(
        investigation_id=row.investigation_id,
        previous_state=InvestigationState(row.previous_state) if row.previous_state else None,
        current_state=InvestigationState(row.current_state),
        transitioned_at=row.transitioned_at,
        reason=row.reason,
        iteration_number=row.iteration_number,
    )
