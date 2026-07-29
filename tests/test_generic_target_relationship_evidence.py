from __future__ import annotations

import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.evidence_execution_service import (
    execute_evidence_plan,
)
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchResult,
    TableMetadata,
)
from legacydb_copilot.services.safe_sql_service import PlannedQuery, plan_safe_queries
from legacydb_copilot.services.verified_evidence_service import (
    normalize_verified_evidence,
)


def _metadata(*tables: TableMetadata) -> MetadataSearchResult:
    return MetadataSearchResult(
        list(tables),
        [],
        [],
        "refreshed",
        engine_type="sql_server",
    )


def test_alphanumeric_business_key_does_not_target_numeric_identity() -> None:
    table = TableMetadata(
        "hr.WorkerBenefit",
        ["WorkerBenefitId", "BenefitNumber", "BusinessKey", "Status"],
        20,
        ["WorkerBenefitId"],
        [],
        [],
        column_types={
            "WorkerBenefitId": "INTEGER",
            "BenefitNumber": "NVARCHAR(40)",
            "BusinessKey": "NVARCHAR(40)",
            "Status": "NVARCHAR(20)",
        },
    )

    plan = plan_safe_queries(
        InvestigationIntent.PROCESS_FLOW_BREAK,
        _metadata(table),
        extract_entities("Investigate benefit BEN-2042 stuck in review"),
    )

    status = next(item for item in plan if item.purpose.startswith("Confirm current status"))
    assert "BEN-2042" in status.sql
    assert "CAST(WorkerBenefitId" not in status.sql
    assert any(name in status.sql for name in ("BenefitNumber", "BusinessKey"))
    assert "BEN-2042" not in status.execution_sql
    assert ":investigation_value_1" in status.execution_sql
    assert status.parameters == {"investigation_value_1": "BEN-2042"}


def test_unrelated_numeric_identifier_is_excluded_from_entity_predicate() -> None:
    table = TableMetadata(
        "hr.CompensationCycle",
        ["CompensationCycleId", "BusinessKey", "Status"],
        10,
        ["CompensationCycleId"],
        [],
        [],
        column_types={
            "CompensationCycleId": "BIGINT",
            "BusinessKey": "VARCHAR(50)",
            "Status": "VARCHAR(20)",
        },
    )

    plan = plan_safe_queries(
        InvestigationIntent.PRODUCTION_INVESTIGATION,
        _metadata(table),
        extract_entities("Inspect compensation cycle CYCLE-A17"),
    )

    entity_query = next(
        item for item in plan if item.purpose.startswith("Prove requested entity")
    )
    assert "CAST(BusinessKey AS NVARCHAR(MAX)) = 'CYCLE-A17'" in entity_query.sql
    assert "CAST(CompensationCycleId" not in entity_query.sql
    assert entity_query.sql.count("'CYCLE-A17'") == 1


def test_unenriched_name_similarity_does_not_create_relationship_plan() -> None:
    parent = TableMetadata(
        "ops.CaseHeader",
        ["CaseHeaderId", "BusinessKey"],
        10,
        ["CaseHeaderId"],
        [],
        [],
        enrichment_loaded=False,
        relationship_metadata_status="not_loaded",
    )
    child = TableMetadata(
        "ops.CaseAction",
        ["CaseActionId", "CaseHeaderId", "BusinessKey"],
        9,
        ["CaseActionId"],
        [],
        [],
        enrichment_loaded=False,
        relationship_metadata_status="not_loaded",
    )

    plan = plan_safe_queries(
        InvestigationIntent.MISSING_DATA,
        _metadata(parent, child),
        extract_entities("Why is action data missing for case CASE-A17?"),
    )

    assert not any(" JOIN " in item.sql.upper() for item in plan)
    assert not any(item.purpose == "Confirmed Missing Related Record Candidates" for item in plan)


def test_declared_relationship_remains_available_for_later_expansion() -> None:
    parent = TableMetadata(
        "ops.CaseHeader",
        ["CaseHeaderId", "BusinessKey"],
        10,
        ["CaseHeaderId"],
        [],
        [],
    )
    child = TableMetadata(
        "ops.CaseAction",
        ["CaseActionId", "CaseHeaderId", "BusinessKey"],
        9,
        ["CaseActionId"],
        [
            {
                "columns": ["CaseHeaderId"],
                "referred_table": "ops.CaseHeader",
                "referred_columns": ["CaseHeaderId"],
            }
        ],
        [],
    )

    plan = plan_safe_queries(
        InvestigationIntent.MISSING_DATA,
        _metadata(parent, child),
        extract_entities("Why is action data missing for case CASE-A17?"),
    )

    assert any(" JOIN " in item.sql.upper() for item in plan)


class _Connector:
    database_engine = "sql_server"

    def __init__(self, result):
        self.result = result

    def execute_read_only_query(self, sql: str, limit: int):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class _ParameterConnector:
    database_engine = "sql_server"

    def __init__(self):
        self.calls = []

    def execute_read_only_query(
        self,
        sql: str,
        limit: int,
        parameters: dict | None = None,
    ):
        self.calls.append((sql, limit, parameters))
        return [{"BusinessKey": parameters["investigation_value_1"]}]


def test_execution_uses_bound_parameters(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "true")
    connector = _ParameterConnector()
    query = PlannedQuery(
        "Inspect one entity",
        "SELECT BusinessKey FROM BenefitEnrollment WHERE BusinessKey = 'BEN-A17'",
        execution_sql=(
            "SELECT BusinessKey FROM BenefitEnrollment "
            "WHERE BusinessKey = :investigation_value_1"
        ),
        parameters={"investigation_value_1": "BEN-A17"},
    )

    evidence = execute_evidence_plan(connector, [query])

    executed_sql, _, parameters = connector.calls[0]
    assert "BEN-A17" not in executed_sql
    assert parameters == {"investigation_value_1": "BEN-A17"}
    assert evidence[0].rows == [{"BusinessKey": "BEN-A17"}]


def test_null_value_rows_are_not_normalized_as_absent(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "true")
    result = execute_evidence_plan(
        _Connector([{"EffectiveDate": None}]),
        [
            PlannedQuery(
                "Prove requested condition",
                "SELECT EffectiveDate FROM BenefitEnrollment WHERE EffectiveDate IS NULL",
                evidence_semantics="null_value",
            )
        ],
    )[0]

    normalized = normalize_verified_evidence([result])
    assert result.evidence_semantics == "null_value"
    assert result.zero_row_result is False
    assert normalized.evidence_categories == ["null_value_rows"]


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_gap"),
    [
        (PermissionError("permission denied"), "permission_denied", "permission_denied_query"),
        (TimeoutError("timed out"), "timed_out", "timed_out_query"),
        (RuntimeError("driver failed"), "failed", "failed_query"),
    ],
)
def test_execution_failures_remain_distinct_from_absence(
    monkeypatch,
    error: Exception,
    expected_status: str,
    expected_gap: str,
) -> None:
    monkeypatch.setenv("ALLOW_FULL_TABLE_SCAN", "true")
    result = execute_evidence_plan(
        _Connector(error),
        [
            PlannedQuery(
                "Check related records",
                "SELECT BusinessKey FROM BenefitEnrollment WHERE BusinessKey IS NULL",
                evidence_semantics="verified_absence",
            )
        ],
    )[0]

    normalized = normalize_verified_evidence([result])
    assert result.execution_status == expected_status
    assert result.evidence_semantics == "execution_failure"
    assert result.zero_row_result is False
    assert normalized.verified_evidence_count == 0
    assert normalized.evidence_gaps == [expected_gap]
