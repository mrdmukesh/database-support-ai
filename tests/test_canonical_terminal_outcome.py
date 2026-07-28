from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from evaluation.agentic_benchmark.models import (
    AgenticScenarioCapture,
    GroundTruthStatus,
    ProtectedGroundTruth,
)
from evaluation.agentic_benchmark.scoring import score_scenario
from evaluation.runners.investigation_reader import InvestigationPersistenceReader
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    InvestigationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.investigation_state_machine import (
    InvestigationState,
    InvestigationStateService,
)


def _resolve(**signals: object) -> str | None:
    from legacydb_copilot.services.terminal_outcome_service import (
        resolve_canonical_terminal_outcome,
    )

    return resolve_canonical_terminal_outcome(**signals)


@pytest.mark.parametrize(
    ("signals", "expected"),
    [
        (
            {
                "reproduction_status": "reproduced",
                "reasoning_permission": "ALLOW_REASONING",
                "root_cause_requirements_satisfied": True,
            },
            "ROOT_CAUSE_CONFIRMED",
        ),
        ({"reproduction_status": "not_reproduced"}, "ISSUE_NOT_REPRODUCED"),
        ({"ai_outcome": "insufficient_evidence"}, "INSUFFICIENT_EVIDENCE"),
        ({"policy_blocked": True}, "POLICY_BLOCKED"),
    ],
)
def test_structured_outcome_signals_resolve_to_canonical_state(
    signals: dict[str, object],
    expected: str,
) -> None:
    assert _resolve(**signals) == expected


def test_ai_answered_alone_does_not_confirm_root_cause() -> None:
    assert _resolve(workflow_status="AI_ANSWERED") is None


def _persisted_investigation(
    *,
    status: str,
    debug_trace: dict | None = None,
) -> tuple[sessionmaker[Session], InvestigationModel]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        organization = OrganizationModel(
            id="org-terminal",
            name="Terminal Org",
            slug="terminal-org",
        )
        workspace = WorkspaceModel(
            id="workspace-terminal",
            organization_id=organization.id,
            name="Terminal Workspace",
            slug="terminal-workspace",
        )
        user = UserModel(
            id="user-terminal",
            organization_id=organization.id,
            email="terminal@example.test",
            role="organization_admin",
        )
        investigation = InvestigationModel(
            id="investigation-terminal",
            organization_id=organization.id,
            workspace_id=workspace.id,
            created_by_id=user.id,
            user_question="Investigate the reported condition",
            status=status,
            environment_type="TEST",
            policy_name="test_readonly",
            safety_profile="NON_PRODUCTION_DEEP_READ_ONLY",
            environment_source="Registered connection metadata",
            environment_snapshot_json="{}",
            environment_telemetry_json="{}",
            ai_debug_trace_json=json.dumps(debug_trace or {}),
        )
        db.add_all((organization, workspace, user, investigation))
        db.commit()
        return factory, investigation


def test_persistence_reader_prefers_canonical_state_transition() -> None:
    factory, investigation = _persisted_investigation(status="AI_ANSWERED")
    with factory() as db:
        persisted = db.get(InvestigationModel, investigation.id)
        assert persisted is not None
        states = InvestigationStateService(db)
        states.initialize(persisted)
        states.transition(
            persisted,
            InvestigationState.EVIDENCE_ASSESSMENT,
            reason="Assess verified evidence.",
        )
        states.transition(
            persisted,
            InvestigationState.ROOT_CAUSE_CONFIRMED,
            reason="Causal evidence verified.",
        )
        db.commit()

    detail = InvestigationPersistenceReader(factory).read(
        investigation.id,
        organization_id=investigation.organization_id,
        workspace_id=investigation.workspace_id,
    )

    assert detail["terminal_state"] == "ROOT_CAUSE_CONFIRMED"


def test_legacy_investigation_uses_narrow_structured_compatibility() -> None:
    factory, investigation = _persisted_investigation(
        status="AI_SUMMARIZED_NOT_REPRODUCED",
        debug_trace={
            "reasoning_mode": "EVIDENCE_SUMMARY_NOT_REPRODUCED",
            "ai_outcome": "evidence_summary_not_reproduced",
        },
    )

    detail = InvestigationPersistenceReader(factory).read(
        investigation.id,
        organization_id=investigation.organization_id,
        workspace_id=investigation.workspace_id,
    )

    assert detail["terminal_state"] == "ISSUE_NOT_REPRODUCED"


def _truth(expected: str) -> ProtectedGroundTruth:
    return ProtectedGroundTruth(
        scenario_id="general-terminal-contract",
        review_status=GroundTruthStatus.REVIEWED,
        expected_terminal_states=(expected,),
    )


def test_unknown_legacy_state_remains_a_benchmark_mismatch() -> None:
    capture = AgenticScenarioCapture(
        scenario_id="general-terminal-contract",
        database="DemoDatabase",
        domain="general",
        question="Investigate",
        terminal_state="LEGACY_UNKNOWN_OUTCOME",
    )

    result = score_scenario(capture, _truth("ROOT_CAUSE_CONFIRMED"))

    assert "unexpected_terminal_state" in result.defects


def test_benchmark_terminal_comparison_remains_exact() -> None:
    matching = AgenticScenarioCapture(
        scenario_id="general-terminal-contract",
        database="DemoDatabase",
        domain="general",
        question="Investigate",
        terminal_state="ROOT_CAUSE_CONFIRMED",
    )
    different_case = AgenticScenarioCapture(
        scenario_id="general-terminal-contract",
        database="DemoDatabase",
        domain="general",
        question="Investigate",
        terminal_state="root_cause_confirmed",
    )

    matching_result = score_scenario(matching, _truth("ROOT_CAUSE_CONFIRMED"))
    different_case_result = score_scenario(
        different_case,
        _truth("ROOT_CAUSE_CONFIRMED"),
    )

    assert "unexpected_terminal_state" not in matching_result.defects
    assert "unexpected_terminal_state" in different_case_result.defects
