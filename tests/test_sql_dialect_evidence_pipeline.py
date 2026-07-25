from __future__ import annotations

import pytest

from legacydb_copilot.services.evidence_execution_service import execute_evidence_plan
from legacydb_copilot.services.safe_sql_service import PlannedQuery, ProductionReadSafetyValidator
from legacydb_copilot.services.sql_dialect_service import (
    SqlDialect,
    SqlDialectValidationError,
    apply_row_limit,
    resolve_sql_dialect,
    validate_sql_dialect,
)


@pytest.mark.parametrize("provider", ["sql_server", "mssql", "azure_sql", "Azure SQL"])
def test_sql_server_aliases_generate_tsql_without_limit(provider: str) -> None:
    dialect = resolve_sql_dialect(provider)
    sql = apply_row_limit("SELECT EmployeeId FROM dbo.EmployeeHistory", 100, dialect)
    assert sql == "SELECT TOP (100) EmployeeId FROM dbo.EmployeeHistory"
    assert "LIMIT" not in sql.upper()


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("postgresql", "SELECT PaymentId FROM Payment LIMIT 100"),
        ("mysql", "SELECT PaymentId FROM Payment LIMIT 100"),
        ("sqlite", "SELECT PaymentId FROM Payment LIMIT 100"),
        ("oracle", "SELECT PaymentId FROM Payment FETCH FIRST 100 ROWS ONLY"),
    ],
)
def test_provider_specific_row_limits(provider: str, expected: str) -> None:
    assert apply_row_limit(
        "SELECT PaymentId FROM Payment", 100, resolve_sql_dialect(provider)
    ) == expected


def test_ordered_sql_server_offset_fetch_is_preserved() -> None:
    sql = (
        "SELECT EmployeeHistoryId FROM dbo.EmployeeHistory "
        "ORDER BY EmployeeHistoryId OFFSET 0 ROWS FETCH NEXT 100 ROWS ONLY"
    )
    assert apply_row_limit(sql, 100, SqlDialect.SQL_SERVER) == sql


def test_existing_parenthesized_sql_server_top_is_unchanged() -> None:
    sql = "SELECT TOP (100) EmployeeHistoryId FROM dbo.EmployeeHistory"
    assert apply_row_limit(sql, 100, SqlDialect.SQL_SERVER) == sql


def test_sql_server_select_without_top_receives_parenthesized_top() -> None:
    assert apply_row_limit(
        "SELECT EmployeeHistoryId FROM dbo.EmployeeHistory",
        100,
        SqlDialect.SQL_SERVER,
    ) == "SELECT TOP (100) EmployeeHistoryId FROM dbo.EmployeeHistory"


def test_sql_server_row_limit_transformation_is_idempotent() -> None:
    original = "SELECT EmployeeHistoryId FROM dbo.EmployeeHistory"
    once = apply_row_limit(original, 100, SqlDialect.SQL_SERVER)
    twice = apply_row_limit(once, 100, SqlDialect.SQL_SERVER)
    three_times = apply_row_limit(twice, 100, SqlDialect.SQL_SERVER)
    assert once == twice == three_times
    assert once.upper().count("TOP") == 1


def test_unknown_provider_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing or unsupported"):
        resolve_sql_dialect(None)
    with pytest.raises(ValueError, match="missing or unsupported"):
        resolve_sql_dialect("unknown")


def test_sql_server_limit_rejected_with_structured_diagnostic() -> None:
    with pytest.raises(SqlDialectValidationError) as caught:
        validate_sql_dialect(
            "SELECT EmployeeId FROM dbo.EmployeeHistory LIMIT 100",
            SqlDialect.SQL_SERVER,
            planner_step="evidence_execution_preflight",
            query_id="Q-EMPLOYEE",
        )
    assert caught.value.diagnostic.provider == "sql_server"
    assert caught.value.diagnostic.invalid_token == "LIMIT"
    assert caught.value.diagnostic.planner_step == "evidence_execution_preflight"
    assert caught.value.diagnostic.query_id == "Q-EMPLOYEE"


@pytest.mark.parametrize("provider", ["postgresql", "mysql"])
def test_top_rejected_for_limit_dialects(provider: str) -> None:
    with pytest.raises(SqlDialectValidationError) as caught:
        validate_sql_dialect(
            "SELECT TOP (100) PaymentId FROM Payment",
            resolve_sql_dialect(provider),
            planner_step="planner",
            query_id="Q-PAYMENT",
        )
    assert caught.value.diagnostic.invalid_token == "TOP"


def test_invalid_sql_server_query_never_reaches_connector() -> None:
    class Connector:
        database_engine = "sql_server"
        called = False

        def execute_read_only_query(self, sql: str, limit: int = 100) -> list[dict]:
            self.called = True
            return []

    connector = Connector()
    statuses: list[dict] = []
    result = execute_evidence_plan(
        connector,
        [PlannedQuery("employee history", "SELECT * FROM dbo.EmployeeHistory LIMIT 100", query_id="Q-1")],
        plan_statuses=statuses,
    )
    assert connector.called is False
    assert result[0].error and "invalid sql dialect token" in result[0].error.lower()
    assert "provider sql_server" in statuses[0]["reason"]


def test_payroll_evidence_queries_use_tsql_and_reach_evidence_collection(monkeypatch) -> None:
    class Connector:
        database_engine = "sql_server"

        def estimate_table_rows(self, _table_name: str) -> int:
            return 25

        def execute_read_only_query(self, sql: str, limit: int = 100) -> list[dict]:
            assert "LIMIT" not in sql.upper()
            assert sql.startswith("SELECT TOP (100)")
            return [{"verified": True}]

    monkeypatch.setenv("MAX_INVESTIGATION_ROWS", "100")
    plan = [
        PlannedQuery("Employee history", "SELECT EmployeeHistoryId FROM dbo.EmployeeHistory", query_id="Q-1"),
        PlannedQuery("Payroll items", "SELECT PayrollItemId FROM dbo.PayrollItem", query_id="Q-2"),
        PlannedQuery("Workflow", "SELECT WorkflowStepId FROM dbo.WorkflowStep", query_id="Q-3"),
        PlannedQuery("Payments", "SELECT PaymentId FROM dbo.Payment", query_id="Q-4"),
    ]
    evidence = execute_evidence_plan(Connector(), plan, provider="sql_server")
    assert len(evidence) == 4
    assert all(item.rows == [{"verified": True}] and item.error is None for item in evidence)


@pytest.mark.parametrize(
    ("question", "provider", "expected_token"),
    [
        ("Use LIMIT when investigating employees", "sql_server", "TOP (100)"),
        ("Use TOP when investigating employees", "postgresql", "LIMIT 100"),
    ],
)
def test_user_wording_cannot_override_connection_provider(
    question: str, provider: str, expected_token: str
) -> None:
    del question
    sql = apply_row_limit("SELECT EmployeeId FROM Employee", 100, resolve_sql_dialect(provider))
    assert expected_token in sql


def test_production_scan_protection_uses_trusted_sql_server_dialect() -> None:
    result = ProductionReadSafetyValidator(
        max_rows=100,
        row_estimates={"dbo.employeehistory": 25},
        engine_type="sql_server",
    ).validate("SELECT EmployeeId FROM dbo.EmployeeHistory")
    assert result.sql.startswith("SELECT TOP (100)")
    assert "LIMIT" not in result.sql.upper()
