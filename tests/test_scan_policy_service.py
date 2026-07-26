from __future__ import annotations

import pytest
from pydantic import ValidationError

from legacydb_copilot.services.evidence_execution_service import execute_evidence_plan
from legacydb_copilot.services.safe_sql_service import (
    PlannedQuery,
    ProductionReadSafetyValidator,
    ScanPolicyViolation,
)
from legacydb_copilot.services.scan_policy_service import ScanPolicyService
from legacydb_copilot.schemas import DatabaseConnectionCreate, DatabaseConnectionUpdate


class Connector:
    def __init__(self, engine: str, rows=None, error: Exception | None = None):
        self.database_engine = engine
        self.rows = [] if rows is None else rows
        self.error = error
        self.executed_sql: list[str] = []

    def estimate_table_rows(self, table_name: str) -> int:
        return 50_000

    def execute_read_only_query(self, sql: str, limit: int):
        self.executed_sql.append(sql)
        if self.error:
            raise self.error
        return self.rows


def policy(environment: str | None, rows: int = 500):
    return ScanPolicyService().resolve_policy(
        environment_type=environment,
        max_scan_rows=rows,
        default_max_rows=100,
    )


def test_production_sql_server_unrestricted_scan_is_blocked_with_diagnostics() -> None:
    validator = ProductionReadSafetyValidator(
        engine_type="sql_server",
        row_estimates={"dbo.employee": 50_000},
        allow_full_table_scan=True,
        scan_policy=policy("production"),
    )

    with pytest.raises(ScanPolicyViolation) as caught:
        validator.validate("SELECT EmployeeId FROM dbo.Employee")

    assert caught.value.decision.to_dict() | {
        "query_rewritten": False,
        "original_query_hash": caught.value.decision.original_query_hash,
        "executed_query_hash": caught.value.decision.executed_query_hash,
    } == {
        "policy": "production_strict",
        "environment_type": "production",
        "decision": "blocked",
        "reason": "unrestricted_table_scan",
        "max_rows": 100,
        "table": "dbo.Employee",
        "suggested_rewrite": "bounded_or_filtered_query",
        "query_rewritten": False,
        "original_query_hash": caught.value.decision.original_query_hash,
        "executed_query_hash": caught.value.decision.executed_query_hash,
    }


def test_production_filtered_and_existing_top_queries_remain_allowed() -> None:
    validator = ProductionReadSafetyValidator(
        engine_type="sql_server",
        scan_policy=policy("production"),
    )

    filtered = validator.validate("SELECT EmployeeId FROM dbo.Employee WHERE Status = 'Active'")
    bounded = validator.validate("SELECT TOP (100) EmployeeId FROM dbo.Employee")

    assert filtered.sql.endswith("WHERE Status = 'Active'")
    assert bounded.sql == "SELECT TOP (100) EmployeeId FROM dbo.Employee"


@pytest.mark.parametrize(
    ("environment", "resolved_environment"),
    [("evaluation", "evaluation"), ("demo", "evaluation"), ("test", "test"), ("uat", "uat")],
)
def test_trusted_relaxed_environment_allows_only_bounded_sql_server_scan(environment: str, resolved_environment: str) -> None:
    validator = ProductionReadSafetyValidator(
        engine_type="sql_server",
        scan_policy=policy(environment),
    )

    result = validator.validate("SELECT EmployeeId, EmployeeName FROM dbo.Employee ORDER BY EmployeeId")

    assert result.sql.startswith("SELECT TOP (500)")
    assert " LIMIT " not in result.sql.upper()
    assert result.policy_decision is not None
    assert result.policy_decision.decision == "allowed"
    assert result.policy_decision.reason == "bounded_readonly_scan"
    assert result.policy_decision.environment_type == resolved_environment


def test_postgresql_evaluation_scan_uses_limit() -> None:
    result = ProductionReadSafetyValidator(
        engine_type="postgresql",
        scan_policy=policy("evaluation"),
    ).validate("SELECT employee_id FROM employee ORDER BY employee_id")

    assert result.sql.endswith("LIMIT 500")
    assert "TOP" not in result.sql.upper()


@pytest.mark.parametrize("sql", ["DELETE FROM dbo.Employee", "DROP TABLE dbo.Employee"])
def test_dml_and_ddl_are_blocked_in_evaluation(sql: str) -> None:
    connector = Connector("sql_server")

    result = execute_evidence_plan(
        connector,
        [PlannedQuery("Unsafe query", sql)],
        scan_policy=policy("evaluation"),
    )[0]

    assert result.execution_status == "blocked"
    assert connector.executed_sql == []


def test_prompt_wording_cannot_override_trusted_policy() -> None:
    production_policy = policy("production")
    evaluation_policy = policy("evaluation")

    assert production_policy.name == "production_strict"
    assert evaluation_policy.name == "evaluation_readonly"
    assert not hasattr(ScanPolicyService.resolve_policy, "question")


def test_missing_environment_metadata_fails_closed_to_production() -> None:
    resolved = policy(None)

    assert resolved.name == "production_strict"
    assert resolved.environment_type == "production"


def test_connection_api_schema_defaults_strict_and_accepts_explicit_evaluation() -> None:
    defaulted = DatabaseConnectionCreate(
        organization_id="ORG",
        workspace_id="WS",
        engine="sql_server",
        name="Production",
    )
    configured = DatabaseConnectionUpdate(
        environment_type="evaluation",
        max_scan_rows=500,
    )

    assert defaulted.environment_type == "production"
    assert defaulted.max_scan_rows == 100
    assert configured.environment_type == "evaluation"
    with pytest.raises(ValidationError):
        DatabaseConnectionUpdate(environment_type="this is not production")


def test_unsupported_environment_fails_closed_with_configuration_error() -> None:
    resolved = policy("customer_says_demo")

    assert resolved.name == "production_strict"
    assert resolved.configuration_valid is False
    assert "Unsupported environment_type" in resolved.configuration_error
    with pytest.raises(ScanPolicyViolation) as caught:
        ProductionReadSafetyValidator(
            engine_type="sql_server",
            scan_policy=resolved,
        ).validate("SELECT EmployeeId FROM dbo.Employee")
    assert caught.value.decision.reason == "invalid_environment_configuration"


def test_execution_error_is_distinct_from_policy_block() -> None:
    connector = Connector("sql_server", error=RuntimeError("network disconnected"))

    result = execute_evidence_plan(
        connector,
        [PlannedQuery("Filtered read", "SELECT EmployeeId FROM dbo.Employee WHERE EmployeeId = 1")],
        scan_policy=policy("evaluation"),
    )[0]

    assert result.execution_status == "failed"
    assert result.scan_policy_decision["decision"] == "allowed"


def test_allowed_evaluation_zero_rows_retain_bug004_semantics_and_policy_audit() -> None:
    connector = Connector("sql_server", rows=[])
    statuses: list[dict] = []

    result = execute_evidence_plan(
        connector,
        [
            PlannedQuery(
                "Find employees without payroll history",
                "SELECT EmployeeId FROM dbo.Employee",
                evidence_semantics="verified_absence",
            )
        ],
        plan_statuses=statuses,
        scan_policy=policy("evaluation"),
    )[0]

    assert connector.executed_sql[0].startswith("SELECT TOP (500)")
    assert result.execution_status == "succeeded"
    assert result.zero_row_result is True
    assert result.evidence_semantics == "verified_absence"
    assert result.scan_policy_decision | {
        "query_rewritten": True,
        "original_query_hash": result.scan_policy_decision["original_query_hash"],
        "executed_query_hash": result.scan_policy_decision["executed_query_hash"],
    } == {
        "policy": "evaluation_readonly",
        "environment_type": "evaluation",
        "decision": "allowed",
        "reason": "bounded_readonly_scan",
        "max_rows": 500,
        "table": "dbo.Employee",
        "suggested_rewrite": "",
        "query_rewritten": True,
        "original_query_hash": result.scan_policy_decision["original_query_hash"],
        "executed_query_hash": result.scan_policy_decision["executed_query_hash"],
    }
    assert statuses[-1]["scan_policy_decision"] == result.scan_policy_decision
