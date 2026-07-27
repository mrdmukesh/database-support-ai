from __future__ import annotations

import json
from collections import deque

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.config import Settings
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    InvestigationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.agentic_investigation_loop import (
    AgenticLoopLimits,
    LoopAssessment,
    MultiStepAgenticInvestigationLoop,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.investigation_state_machine import InvestigationState
from legacydb_copilot.services.safe_investigation_planner import (
    EntityScope,
    EnvironmentPolicy,
    EvidenceRequest,
    EvidenceRequestType,
)
from legacydb_copilot.services.safe_sql_service import PlannedQuery, validate_read_only_sql


class SequenceAssessor:
    def __init__(self, *assessments: LoopAssessment):
        self.assessments = deque(assessments)
        self.calls = 0

    def assess(self, _evidence):
        self.calls += 1
        return self.assessments.popleft()


class FakePipeline:
    def __init__(self, outcomes: dict[str, str] | None = None):
        self.outcomes = outcomes or {}
        self.calls: list[tuple[str, str]] = []

    def plan(self, request):
        self.calls.append(("plan", request.entity_key))
        return (
            PlannedQuery(
                purpose=request.unresolved_question,
                sql=f"SELECT id FROM PayrollItems WHERE id = '{request.entity_key}'",
            ),
        )

    def validate(self, queries):
        self.calls.append(("validate", queries[0].purpose))
        for query in queries:
            validate_read_only_sql(query.sql)
        return queries

    def execute(self, queries):
        key = queries[0].sql.rsplit("'", 2)[1]
        self.calls.append(("execute", key))
        outcome = self.outcomes.get(key, "succeeded")
        if outcome == "failed":
            return (
                EvidenceResult(
                    purpose=queries[0].purpose,
                    sql=queries[0].sql,
                    rows=[],
                    error="classified permanent failure",
                    execution_status="failed",
                    evidence_semantics="execution_failure",
                ),
            )
        return (
            EvidenceResult(
                purpose=queries[0].purpose,
                sql=queries[0].sql,
                rows=[{"id": key}],
                execution_status="succeeded",
                evidence_semantics="positive_rows",
                evidence_relevance="relevant",
            ),
        )


def evidence_request(
    key: str,
    question: str,
    request_type: EvidenceRequestType,
) -> EvidenceRequest:
    return EvidenceRequest(
        request_type=request_type,
        unresolved_question=question,
        entity_scope=EntityScope.EXACT_KEY,
        entity_type="PayrollItem",
        entity_key=key,
        expected_information_gain=0.9,
    )


def assessment(*requests: EvidenceRequest) -> LoopAssessment:
    return LoopAssessment(
        candidates=requests,
        gap_analysis={
            "status": "GAPS_IDENTIFIED",
            "gaps": [
                {"question_type": item.unresolved_question, "source_type": "DATABASE"}
                for item in requests
            ],
        },
    )


def terminal(state: InvestigationState, reason: str) -> LoopAssessment:
    return LoopAssessment(
        candidates=(),
        gap_analysis={"status": "COMPLETE", "gaps": []},
        terminal_state=state,
        terminal_reason=reason,
    )


@pytest.fixture
def investigation_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        organization = OrganizationModel(name="Agentic Test", slug="agentic-test")
        workspace = WorkspaceModel(
            organization=organization,
            name="DemoPayrollV2",
            slug="demo-payroll-v2",
        )
        user = UserModel(
            organization=organization,
            email="agentic@example.test",
            password_hash="x",
            full_name="Agentic Test",
        )
        db.add_all((organization, workspace, user))
        db.flush()
        investigation = InvestigationModel(
            organization_id=organization.id,
            workspace_id=workspace.id,
            created_by_id=user.id,
            user_question="Why is PayrollItem PI-404 missing?",
            environment_type="evaluation",
            policy_name="evaluation_readonly",
        )
        db.add(investigation)
        db.flush()
        yield db, investigation


def run_loop(db, investigation, assessor, pipeline, **limit_overrides):
    limits = {
        "max_iterations": 5,
        "max_sql_queries": 5,
        "max_total_rows": 20,
        "max_execution_seconds": 30,
        "max_llm_calls": 2,
        "max_tokens": 100,
        "max_retries": 1,
    }
    limits.update(limit_overrides)
    return MultiStepAgenticInvestigationLoop(
        db,
        assessor=assessor,
        pipeline=pipeline,
        policy=EnvironmentPolicy("evaluation", "evaluation_readonly"),
        limits=AgenticLoopLimits(**limits),
    ).run(investigation)


def test_two_successful_iterations_reach_confirmed_root_cause(investigation_db) -> None:
    db, investigation = investigation_db
    entity = evidence_request("PI-404", "AFFECTED_ENTITY", EvidenceRequestType.ENTITY_LOOKUP)
    workflow = evidence_request("WF-404", "WORKFLOW", EvidenceRequestType.WORKFLOW_TRACE)
    assessor = SequenceAssessor(
        assessment(entity, workflow),
        assessment(workflow),
        terminal(InvestigationState.ROOT_CAUSE_CONFIRMED, "Verified workflow break."),
    )

    result = run_loop(db, investigation, assessor, FakePipeline())

    assert result.terminal_state is InvestigationState.ROOT_CAUSE_CONFIRMED
    assert result.budget.iterations == 2
    assert result.budget.sql_queries == 2
    assert len(result.steps) == 2
    assert [step.iteration_number for step in result.steps] == [1, 2]
    assert json.loads(result.steps[0].evidence_json)[0]["rows"] == [{"id": "PI-404"}]


def test_failed_action_is_followed_by_successful_alternative(investigation_db) -> None:
    db, investigation = investigation_db
    failed = evidence_request("PI-BAD", "ACTUAL_STATE", EvidenceRequestType.STATUS_HISTORY)
    alternative = evidence_request(
        "PI-GOOD", "RELATIONSHIPS", EvidenceRequestType.RELATED_RECORDS
    )
    assessor = SequenceAssessor(
        assessment(failed, alternative),
        assessment(failed, alternative),
        terminal(InvestigationState.ROOT_CAUSE_CONFIRMED, "Alternative evidence verified."),
    )
    pipeline = FakePipeline({"PI-BAD": "failed"})

    result = run_loop(db, investigation, assessor, pipeline)

    assert [step.outcome for step in result.steps] == ["FAILED_PERMANENT", "SUCCEEDED"]
    assert ("execute", "PI-BAD") in pipeline.calls
    assert ("execute", "PI-GOOD") in pipeline.calls
    assert result.terminal_state is InvestigationState.ROOT_CAUSE_CONFIRMED


def test_duplicate_action_is_suppressed(investigation_db) -> None:
    db, investigation = investigation_db
    first = evidence_request("PI-1", "AFFECTED_ENTITY", EvidenceRequestType.ENTITY_LOOKUP)
    second = evidence_request("PI-2", "EXPECTED_STATE", EvidenceRequestType.EXPECTED_STATE_CHECK)
    assessor = SequenceAssessor(
        assessment(first, second),
        assessment(first, second),
        terminal(InvestigationState.ROOT_CAUSE_CONFIRMED, "Expected state verified."),
    )
    pipeline = FakePipeline()

    result = run_loop(db, investigation, assessor, pipeline)

    executed = [value for action, value in pipeline.calls if action == "execute"]
    assert executed == ["PI-1", "PI-2"]
    assert result.terminal_state is InvestigationState.ROOT_CAUSE_CONFIRMED


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"max_sql_queries": 1}, InvestigationState.QUERY_BUDGET_EXHAUSTED),
        ({"max_iterations": 1}, InvestigationState.ITERATION_BUDGET_EXHAUSTED),
    ],
)
def test_query_and_iteration_budget_exhaustion(
    investigation_db,
    overrides,
    expected,
) -> None:
    db, investigation = investigation_db
    candidate = evidence_request(
        "PI-1", "AFFECTED_ENTITY", EvidenceRequestType.ENTITY_LOOKUP
    )
    assessor = SequenceAssessor(assessment(candidate), assessment(candidate))

    result = run_loop(db, investigation, assessor, FakePipeline(), **overrides)

    assert result.terminal_state is expected
    assert result.budget.iterations == 1


def test_unknown_root_cause_ends_as_insufficient_evidence_not_failure(
    investigation_db,
) -> None:
    db, investigation = investigation_db
    candidate = evidence_request(
        "PI-1", "AFFECTED_ENTITY", EvidenceRequestType.ENTITY_LOOKUP
    )
    assessor = SequenceAssessor(assessment(candidate), assessment(candidate))

    result = run_loop(db, investigation, assessor, FakePipeline())

    assert result.terminal_state is InvestigationState.INSUFFICIENT_EVIDENCE
    assert result.terminal_state is not InvestigationState.FAILED


def test_issue_not_reproduced_is_a_valid_terminal_state(investigation_db) -> None:
    db, investigation = investigation_db
    assessor = SequenceAssessor(
        terminal(
            InvestigationState.ISSUE_NOT_REPRODUCED,
            "Verified current state does not reproduce the report.",
        )
    )

    result = run_loop(db, investigation, assessor, FakePipeline())

    assert result.terminal_state is InvestigationState.ISSUE_NOT_REPRODUCED
    assert result.steps == ()


def test_cancellation_stops_before_any_sql(investigation_db) -> None:
    db, investigation = investigation_db
    assessor = SequenceAssessor(
        assessment(
            evidence_request(
                "PI-1", "AFFECTED_ENTITY", EvidenceRequestType.ENTITY_LOOKUP
            )
        )
    )
    pipeline = FakePipeline()

    result = MultiStepAgenticInvestigationLoop(
        db,
        assessor=assessor,
        pipeline=pipeline,
        policy=EnvironmentPolicy("evaluation", "evaluation_readonly"),
        limits=AgenticLoopLimits(),
    ).run(investigation, is_cancelled=lambda: True)

    assert result.terminal_state is InvestigationState.CANCELLED
    assert pipeline.calls == []


def test_existing_non_agentic_mode_remains_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("FEATURE_AGENTIC_INVESTIGATION_ENABLED", raising=False)

    assert Settings.from_env().feature_agentic_investigation_enabled is False


def test_all_loop_limits_are_configurable(monkeypatch) -> None:
    values = {
        "AGENTIC_MAX_ITERATIONS": "3",
        "AGENTIC_MAX_SQL_QUERIES": "4",
        "AGENTIC_MAX_TOTAL_ROWS": "50",
        "AGENTIC_MAX_EXECUTION_SECONDS": "6.5",
        "AGENTIC_MAX_LLM_CALLS": "2",
        "AGENTIC_MAX_TOKENS": "700",
        "AGENTIC_MAX_RETRIES": "1",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    limits = AgenticLoopLimits.from_settings(Settings.from_env())

    assert limits == AgenticLoopLimits(3, 4, 50, 6.5, 2, 700, 1)
