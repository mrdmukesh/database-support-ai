from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    AuditLogModel,
    InvestigationModel,
    InvestigationStateTransitionModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.investigation_state_machine import (
    InvalidInvestigationTransition,
    InvestigationState,
    InvestigationStateService,
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


def _add_transition(
    db: Session,
    investigation: InvestigationModel,
    *,
    transition_id: str,
    previous_state: InvestigationState | None,
    current_state: InvestigationState,
    transitioned_at: datetime,
    sequence_number: int | None = None,
) -> None:
    if sequence_number is None:
        sequence_number = (
            db.query(InvestigationStateTransitionModel)
            .filter_by(investigation_id=investigation.id)
            .count()
            + 1
        )
    db.add(
        InvestigationStateTransitionModel(
            id=transition_id,
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            investigation_id=investigation.id,
            previous_state=previous_state.value if previous_state else "",
            current_state=current_state.value,
            transitioned_at=transitioned_at,
            reason=f"Enter {current_state.value}.",
            iteration_number=0,
            sequence_number=sequence_number,
        )
    )
    db.flush()


def test_current_prefers_later_state_when_timestamps_match() -> None:
    db, investigation = _session_and_investigation()
    timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    _add_transition(
        db,
        investigation,
        transition_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        previous_state=None,
        current_state=InvestigationState.INITIALIZATION,
        transitioned_at=timestamp,
    )
    _add_transition(
        db,
        investigation,
        transition_id="00000000-0000-0000-0000-000000000001",
        previous_state=InvestigationState.INITIALIZATION,
        current_state=InvestigationState.EVIDENCE_ASSESSMENT,
        transitioned_at=timestamp,
    )

    current = InvestigationStateService(db).current(investigation.id)

    assert current is not None
    assert current.current_state is InvestigationState.EVIDENCE_ASSESSMENT


@pytest.mark.parametrize(
    ("initialization_id", "assessment_id"),
    [
        (
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "00000000-0000-0000-0000-000000000001",
        ),
        (
            "00000000-0000-0000-0000-000000000001",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
        ),
    ],
)
def test_current_state_is_independent_of_uuid_order(
    initialization_id: str,
    assessment_id: str,
) -> None:
    db, investigation = _session_and_investigation()
    timestamp = datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)
    _add_transition(
        db,
        investigation,
        transition_id=initialization_id,
        previous_state=None,
        current_state=InvestigationState.INITIALIZATION,
        transitioned_at=timestamp,
    )
    _add_transition(
        db,
        investigation,
        transition_id=assessment_id,
        previous_state=InvestigationState.INITIALIZATION,
        current_state=InvestigationState.EVIDENCE_ASSESSMENT,
        transitioned_at=timestamp,
    )

    current = InvestigationStateService(db).current(investigation.id)

    assert current is not None
    assert current.current_state is InvestigationState.EVIDENCE_ASSESSMENT


def test_same_timestamp_sequence_accepts_valid_canonical_transition() -> None:
    db, investigation = _session_and_investigation()
    timestamp = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
    _add_transition(
        db,
        investigation,
        transition_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        previous_state=None,
        current_state=InvestigationState.INITIALIZATION,
        transitioned_at=timestamp,
    )
    _add_transition(
        db,
        investigation,
        transition_id="00000000-0000-0000-0000-000000000001",
        previous_state=InvestigationState.INITIALIZATION,
        current_state=InvestigationState.EVIDENCE_ASSESSMENT,
        transitioned_at=timestamp,
    )

    terminal = InvestigationStateService(db).transition(
        investigation,
        InvestigationState.ROOT_CAUSE_CONFIRMED,
        reason="Verified causal evidence.",
    )

    assert terminal.current_state is InvestigationState.ROOT_CAUSE_CONFIRMED


def test_current_returns_terminal_state_for_full_same_timestamp_sequence() -> None:
    db, investigation = _session_and_investigation()
    timestamp = datetime(2026, 4, 5, 6, 7, 8, tzinfo=UTC)
    _add_transition(
        db,
        investigation,
        transition_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        previous_state=None,
        current_state=InvestigationState.INITIALIZATION,
        transitioned_at=timestamp,
    )
    _add_transition(
        db,
        investigation,
        transition_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        previous_state=InvestigationState.INITIALIZATION,
        current_state=InvestigationState.EVIDENCE_ASSESSMENT,
        transitioned_at=timestamp,
    )
    _add_transition(
        db,
        investigation,
        transition_id="00000000-0000-0000-0000-000000000001",
        previous_state=InvestigationState.EVIDENCE_ASSESSMENT,
        current_state=InvestigationState.ROOT_CAUSE_CONFIRMED,
        transitioned_at=timestamp,
    )

    current = InvestigationStateService(db).current(investigation.id)

    assert current is not None
    assert current.current_state is InvestigationState.ROOT_CAUSE_CONFIRMED


def test_valid_same_timestamp_sequence_commits_without_partial_rollback() -> None:
    db, investigation = _session_and_investigation()
    timestamp = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)
    _add_transition(
        db,
        investigation,
        transition_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        previous_state=None,
        current_state=InvestigationState.INITIALIZATION,
        transitioned_at=timestamp,
    )
    _add_transition(
        db,
        investigation,
        transition_id="00000000-0000-0000-0000-000000000001",
        previous_state=InvestigationState.INITIALIZATION,
        current_state=InvestigationState.EVIDENCE_ASSESSMENT,
        transitioned_at=timestamp,
    )
    service = InvestigationStateService(db)

    service.transition(
        investigation,
        InvestigationState.ROOT_CAUSE_CONFIRMED,
        reason="Verified causal evidence.",
    )
    db.commit()

    assert db.get(InvestigationModel, investigation.id) is not None
    assert len(service.history(investigation.id)) == 3
    assert (
        service.current(investigation.id).current_state
        is InvestigationState.ROOT_CAUSE_CONFIRMED
    )


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
    assert [item.sequence_number for item in history] == list(
        range(1, len(history) + 1)
    )


def test_sequence_starts_at_one_and_increments_contiguously() -> None:
    db, investigation = _session_and_investigation()
    service = InvestigationStateService(db)

    first = service.initialize(investigation)
    second = service.transition(
        investigation,
        InvestigationState.EVIDENCE_ASSESSMENT,
        reason="Assess evidence.",
    )

    assert first.sequence_number == 1
    assert second.sequence_number == 2
    assert service.current(investigation.id).sequence_number == 2
    assert [item.sequence_number for item in service.history(investigation.id)] == [
        1,
        2,
    ]


def test_duplicate_investigation_sequence_is_rejected() -> None:
    db, investigation = _session_and_investigation()
    InvestigationStateService(db).initialize(investigation)
    duplicate = InvestigationStateTransitionModel(
        organization_id=investigation.organization_id,
        workspace_id=investigation.workspace_id,
        investigation_id=investigation.id,
        previous_state=InvestigationState.INITIALIZATION.value,
        current_state=InvestigationState.EVIDENCE_ASSESSMENT.value,
        reason="Duplicate sequence.",
        iteration_number=0,
        sequence_number=1,
    )

    with pytest.raises(IntegrityError):
        db.add(duplicate)
        db.flush()


def test_sequence_collision_is_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, investigation = _session_and_investigation()
    service = InvestigationStateService(db)
    service.initialize(investigation)
    original = service._next_sequence_number
    attempts = 0

    def collide_once(investigation_id: str) -> int:
        nonlocal attempts
        attempts += 1
        return 1 if attempts == 1 else original(investigation_id)

    monkeypatch.setattr(service, "_next_sequence_number", collide_once)

    transition = service.transition(
        investigation,
        InvestigationState.EVIDENCE_ASSESSMENT,
        reason="Retry sequence collision.",
    )

    assert transition.sequence_number == 2
    assert attempts == 2
    assert len(service.history(investigation.id)) == 2


def test_sequence_collision_revalidates_after_concurrent_state_advance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, investigation = _session_and_investigation()
    service = InvestigationStateService(db)
    service.initialize(investigation)
    original = service._next_sequence_number
    attempts = 0

    def collide_then_advance(investigation_id: str) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            db.add(
                InvestigationStateTransitionModel(
                    organization_id=investigation.organization_id,
                    workspace_id=investigation.workspace_id,
                    investigation_id=investigation.id,
                    previous_state=InvestigationState.INITIALIZATION.value,
                    current_state=InvestigationState.EVIDENCE_ASSESSMENT.value,
                    reason="Concurrent winner.",
                    iteration_number=0,
                    sequence_number=2,
                )
            )
            db.flush()
            return 1
        return original(investigation_id)

    monkeypatch.setattr(service, "_next_sequence_number", collide_then_advance)

    with pytest.raises(InvalidInvestigationTransition):
        service.transition(
            investigation,
            InvestigationState.EVIDENCE_ASSESSMENT,
            reason="Stale concurrent retry.",
        )

    assert attempts == 1
    assert [item.current_state for item in service.history(investigation.id)] == [
        InvestigationState.INITIALIZATION,
        InvestigationState.EVIDENCE_ASSESSMENT,
    ]


def test_unrelated_integrity_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, investigation = _session_and_investigation()
    service = InvestigationStateService(db)
    service.initialize(investigation)
    attempts = 0

    def missing_sequence(_investigation_id: str) -> None:
        nonlocal attempts
        attempts += 1
        return None

    monkeypatch.setattr(service, "_next_sequence_number", missing_sequence)

    with pytest.raises(IntegrityError):
        service.transition(
            investigation,
            InvestigationState.EVIDENCE_ASSESSMENT,
            reason="Must propagate.",
        )

    assert attempts == 1


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
