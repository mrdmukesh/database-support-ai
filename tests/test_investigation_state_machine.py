from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    AuditLogModel,
    InvestigationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.investigation_state_machine import (
    InvestigationState,
    InvestigationStateService,
    InvalidInvestigationTransition,
    TerminalInvestigationState,
)


def _session_and_investigation() -> tuple[Session, InvestigationModel]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    organization = OrganizationModel(id="org-state", name="State Org", slug="state-org")
    workspace = WorkspaceModel(
        id="workspace-state",
        organization_id=organization.id,
        name="State Workspace",
        slug="state-workspace",
    )
    user = UserModel(
        id="user-state",
        organization_id=organization.id,
        email="state@example.test",
        role="organization_admin",
    )
    investigation = InvestigationModel(
        id="investigation-state",
        organization_id=organization.id,
        workspace_id=workspace.id,
        created_by_id=user.id,
        user_question="Investigate",
        environment_type="TEST",
        policy_name="test_readonly",
        safety_profile="NON_PRODUCTION_DEEP_READ_ONLY",
        environment_source="Registered connection metadata",
        environment_snapshot_json="{}",
        environment_telemetry_json="{}",
    )
    db.add_all([organization, workspace, user, investigation])
    db.commit()
    return db, investigation


def test_valid_transitions_persist_complete_ordered_history() -> None:
    db, investigation = _session_and_investigation()
    service = InvestigationStateService(db)
    service.initialize(investigation, reason="start")
    states = [
        InvestigationState.EVIDENCE_ASSESSMENT,
        InvestigationState.GAP_IDENTIFICATION,
        InvestigationState.ACTION_SELECTION,
        InvestigationState.PLANNING,
        InvestigationState.VALIDATION,
        InvestigationState.EXECUTION,
        InvestigationState.VERIFICATION,
        InvestigationState.STATE_UPDATE,
        InvestigationState.STOP_EVALUATION,
        InvestigationState.EVIDENCE_ASSESSMENT,
    ]
    for state in states:
        service.transition(investigation, state, reason=f"enter {state.value}")
    db.commit()

    history = service.history(investigation.id)
    assert [item.current_state for item in history] == [
        InvestigationState.INITIALIZATION,
        *states,
    ]
    assert history[0].previous_state is None
    assert all(
        current.previous_state == previous.current_state
        for previous, current in zip(history, history[1:], strict=False)
    )
    assert [item.transitioned_at for item in history] == sorted(
        item.transitioned_at for item in history
    )
    assert history[-1].iteration_number == 1


def test_invalid_transition_is_rejected_without_history_entry() -> None:
    db, investigation = _session_and_investigation()
    service = InvestigationStateService(db)
    service.initialize(investigation)

    try:
        service.transition(
            investigation,
            InvestigationState.EXECUTION,
            reason="skip safety steps",
        )
        raise AssertionError("invalid transition was accepted")
    except InvalidInvestigationTransition:
        pass

    assert len(service.history(investigation.id)) == 1


def test_terminal_state_cannot_execute_another_step() -> None:
    db, investigation = _session_and_investigation()
    service = InvestigationStateService(db)
    service.initialize(investigation)
    service.transition(
        investigation,
        InvestigationState.EVIDENCE_ASSESSMENT,
        reason="assess",
    )
    service.transition(
        investigation,
        InvestigationState.ROOT_CAUSE_CONFIRMED,
        reason="verified claim",
    )

    try:
        service.transition(
            investigation,
            InvestigationState.GAP_IDENTIFICATION,
            reason="must fail",
        )
        raise AssertionError("terminal transition was accepted")
    except TerminalInvestigationState:
        pass


def test_cancellation_and_internal_failure_are_terminal_and_audited() -> None:
    db, cancelled = _session_and_investigation()
    service = InvestigationStateService(db)
    service.initialize(cancelled)
    cancellation = service.cancel(cancelled, reason="cancelled by user")
    assert cancellation.current_state is InvestigationState.CANCELLED

    failed_db, failed = _session_and_investigation()
    failed_service = InvestigationStateService(failed_db)
    failed_service.initialize(failed)
    failure = failed_service.fail(failed, reason="internal component failure")
    assert failure.current_state is InvestigationState.FAILED

    assert db.query(AuditLogModel).filter_by(
        target_id=cancelled.id,
        action="INVESTIGATION_STATE_TRANSITIONED",
    ).count() == 2
