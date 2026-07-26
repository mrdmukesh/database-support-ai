from __future__ import annotations

import pytest

from legacydb_copilot.agents.entity_extraction_agent import (
    EntityExtractionResult,
    ExtractedEntity,
)
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.evidence_execution_service import (
    EvidenceResult,
    execute_evidence_plan,
)
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchResult,
    TableMetadata,
)
from legacydb_copilot.services.safe_sql_service import PlannedQuery


QUESTION = "Investigate employees who do not have corresponding payroll history records"


class Connector:
    database_engine = "sql_server"

    def __init__(self, result):
        self.result = result

    def execute_read_only_query(self, sql: str, limit: int):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class LargeTableConnector(Connector):
    def estimate_table_rows(self, table_name: str) -> int:
        return 10_000


def _focus(object_name: str = "PayrollItem") -> EvidenceFocus:
    return EvidenceFocus(
        affected_object=object_name,
        affected_object_reason="Question names payroll history",
        inferred_business_key=None,
        business_key_reason="",
        write_path_graph=[],
        ranked_procedures=[],
        confirmed_facts=[],
        inferred_findings=[],
        hypotheses=[],
        self_validation=[],
    )


def _metadata() -> MetadataSearchResult:
    return MetadataSearchResult(
        tables=[
            TableMetadata(
                name="PayrollItem",
                columns=["EmployeeId"],
                score=1.0,
                foreign_keys=[{"referred_table": "Employee"}],
            )
        ],
        views=[],
        procedures=[],
        version="test",
        engine_type="sql_server",
    )


def _entities(*entities: ExtractedEntity) -> EntityExtractionResult:
    return EntityExtractionResult(
        entities=list(entities),
        suspected_issue="missing payroll history",
        likely_module="payroll",
    )


def _gate(evidence: list[EvidenceResult], entities=None, focus=None):
    return run_evidence_gate(
        question=QUESTION,
        intent=InvestigationIntent.MISSING_DATA,
        entities=entities or _entities(),
        metadata=_metadata(),
        evidence=evidence,
        evidence_focus=focus or _focus(),
        documents=[],
    )


def test_successful_zero_row_query_is_explicit_verified_absence(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "true")
    query = PlannedQuery(
        "Inspect relevant rows in PayrollItem",
        "SELECT EmployeeId FROM PayrollItem WHERE EmployeeId IS NULL",
        evidence_semantics="verified_absence",
    )

    result = execute_evidence_plan(Connector([]), [query])[0]

    assert result.execution_status == "succeeded"
    assert result.row_count == 0
    assert result.zero_row_result is True
    assert result.evidence_semantics == "verified_absence"
    assert "found no matching rows" in result.supports_claim
    gate = _gate([result])
    assert gate.verified_evidence is True
    assert gate.reasoning_permission == "ALLOW_REASONING"


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (RuntimeError("database unavailable"), "failed"),
        (PermissionError("query blocked by policy"), "blocked"),
        (TimeoutError("query timed out"), "timed_out"),
    ],
)
def test_failed_blocked_and_timed_out_queries_are_not_negative_evidence(
    monkeypatch, error: Exception, expected_status: str
) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "true")
    query = PlannedQuery(
        "Find missing payroll rows",
        "SELECT EmployeeId FROM PayrollItem WHERE EmployeeId IS NULL",
        evidence_semantics="verified_absence",
    )

    result = execute_evidence_plan(Connector(error), [query])[0]

    assert result.execution_status == expected_status
    assert result.zero_row_result is False
    assert result.evidence_semantics == "execution_failure"
    assert _gate([result]).reasoning_permission == "DENY_REASONING"


def test_irrelevant_zero_row_query_cannot_bypass_gate() -> None:
    result = EvidenceResult(
        "Find missing audit events",
        "SELECT event_id FROM AuditEvent WHERE event_id IS NULL",
        [],
        execution_status="succeeded",
        evidence_semantics="verified_absence",
        supports_claim="No audit events matched.",
    )

    assert _gate([result]).reasoning_permission == "DENY_REASONING"


def test_production_scan_rejection_remains_blocked(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "false")
    query = PlannedQuery(
        "Find missing payroll rows",
        "SELECT EmployeeId FROM PayrollItem",
        evidence_semantics="verified_absence",
    )

    result = execute_evidence_plan(LargeTableConnector([]), [query])[0]

    assert result.execution_status == "blocked"
    assert result.zero_row_result is False
    assert result.evidence_semantics == "execution_failure"
    assert _gate([result]).reasoning_permission == "DENY_REASONING"


def test_unresolved_business_key_does_not_erase_relevant_verified_absence() -> None:
    result = EvidenceResult(
        "Find missing payroll rows",
        "SELECT EmployeeId FROM PayrollItem WHERE EmployeeId = 'EMP-1042'",
        [],
        execution_status="succeeded",
        evidence_semantics="verified_absence",
    )
    entities = _entities(ExtractedEntity("business_key", "EMP-1042"))

    gate = _gate([result], entities=entities)

    assert gate.business_key_exists is False
    assert gate.reasoning_permission == "ALLOW_REASONING"
    assert gate.verified_evidence is True


@pytest.mark.parametrize(
    ("sql", "rows"),
    [
        ("SELECT COUNT(*) AS missing_count FROM PayrollItem WHERE EmployeeId IS NULL", [{"missing_count": 0}]),
        (
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM PayrollItem WHERE EmployeeId IS NULL) "
            "THEN 1 ELSE 0 END AS record_exists",
            [{"record_exists": 0}],
        ),
        (
            "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM PayrollItem WHERE EmployeeId IS NULL) "
            "THEN 0 ELSE 1 END AS missing_count",
            [{"missing_count": 0}],
        ),
    ],
)
def test_zero_aggregate_and_existence_results_are_valid_negative_evidence(
    monkeypatch, sql: str, rows: list[dict]
) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "true")
    query = PlannedQuery("Check missing PayrollItem rows", sql)

    result = execute_evidence_plan(Connector(rows), [query])[0]

    assert result.execution_status == "succeeded"
    assert result.evidence_semantics == "aggregate"
    assert _gate([result]).reasoning_permission == "ALLOW_REASONING"


def test_positive_row_behavior_is_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "true")
    query = PlannedQuery(
        "Inspect relevant rows in PayrollItem",
        "SELECT EmployeeId FROM PayrollItem WHERE EmployeeId IS NOT NULL",
    )

    result = execute_evidence_plan(Connector([{"EmployeeId": 42}]), [query])[0]

    assert result.execution_status == "succeeded"
    assert result.row_count == 1
    assert result.zero_row_result is False
    assert result.evidence_semantics == "positive_rows"
    assert _gate([result]).reasoning_permission == "ALLOW_REASONING"


def test_demo_payroll_sql_server_zero_rows_do_not_trigger_no_rows_denial(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "true")
    queries = [
        PlannedQuery(
            "Inspect relevant rows in dbo.EmployeeHistory",
            "SELECT EmployeeId FROM dbo.EmployeeHistory WHERE EmployeeId IS NULL",
            evidence_semantics="verified_absence",
        ),
        PlannedQuery(
            "Inspect relevant rows in dbo.PayrollItem",
            "SELECT EmployeeId FROM dbo.PayrollItem WHERE EmployeeId IS NULL",
            evidence_semantics="verified_absence",
        ),
    ]

    evidence = execute_evidence_plan(Connector([]), queries)
    gate = _gate(evidence)

    assert all(item.execution_status == "succeeded" for item in evidence)
    assert all(item.zero_row_result for item in evidence)
    assert gate.reasoning_permission == "ALLOW_REASONING"
    assert "no verified deterministic SQL rows" not in gate.permission_reason.casefold()
