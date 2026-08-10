from __future__ import annotations

import pytest

from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.evidence_verification_agent import (
    _metadata_verification_sql,
    _suggest_affected_object,
    _suggest_parent_object,
    execute_verification_check,
)
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchResult,
    TableMetadata,
)
from legacydb_copilot.services.safe_sql_service import validate_read_only_sql


def _focus(name: str = "dbo.Sales") -> EvidenceFocus:
    return EvidenceFocus(
        affected_object=name,
        affected_object_reason="Resolved from metadata.",
        inferred_business_key=None,
        business_key_reason="",
        write_path_graph=[],
        ranked_procedures=[],
        confirmed_facts=[],
        inferred_findings=[],
        hypotheses=[],
        self_validation=[],
    )


def _metadata(engine: str, name: str = "dbo.Sales") -> MetadataSearchResult:
    return MetadataSearchResult(
        tables=[TableMetadata(name, ["SaleId"], 1.0)],
        views=[],
        procedures=[],
        version="test",
        engine_type=engine,
    )


def test_sql_server_affected_object_uses_bound_catalog_query() -> None:
    check = _suggest_affected_object(_metadata("sql_server"), _focus())

    assert "INFORMATION_SCHEMA.COLUMNS" in check.verification_sql
    assert "DESCRIBE" not in check.verification_sql
    assert "dbo" not in check.verification_sql
    assert "Sales" not in check.verification_sql
    assert check.parameters == {"schema_name": "dbo", "table_name": "Sales"}
    validate_read_only_sql(check.verification_sql, engine_type="sql_server")


def test_sql_server_unqualified_object_uses_default_schema_parameter() -> None:
    sql, parameters, supported = _metadata_verification_sql("Sales", "sql_server")

    assert supported is True
    assert parameters == {"schema_name": "dbo", "table_name": "Sales"}
    assert ":schema_name" in sql and ":table_name" in sql


def test_sql_server_alias_uses_same_catalog_strategy() -> None:
    sql, parameters, supported = _metadata_verification_sql("dbo.Sales", "mssql")

    assert supported is True
    assert "INFORMATION_SCHEMA.COLUMNS" in sql
    assert parameters == {"schema_name": "dbo", "table_name": "Sales"}


def test_sql_server_parent_fallback_uses_catalog_query() -> None:
    evidence = [
        EvidenceResult(
            "relationship",
            "SELECT p.SaleId FROM dbo.Sales p JOIN dbo.Payments c ON c.SaleId = p.SaleId",
            [],
        )
    ]

    check = _suggest_parent_object(evidence, _focus("dbo.Orders"), "sql_server")

    assert check is not None
    assert "INFORMATION_SCHEMA.COLUMNS" in check.verification_sql
    assert check.parameters == {"schema_name": "dbo", "table_name": "sales"}


@pytest.mark.parametrize("statement", ["DESCRIBE dbo.Sales", "SHOW TABLES"])
def test_sql_server_rejects_foreign_dialect_metadata_statements(statement: str) -> None:
    with pytest.raises(ValueError, match="not supported"):
        validate_read_only_sql(statement, engine_type="sql_server")


def test_mysql_preserves_describe_and_validator_accepts_it() -> None:
    check = _suggest_affected_object(_metadata("mysql"), _focus())

    assert check.verification_sql == "DESCRIBE dbo.Sales"
    assert check.parameters == {}
    validate_read_only_sql(check.verification_sql, engine_type="mysql")


@pytest.mark.parametrize(
    "object_name",
    ["dbo.Sales; DROP TABLE dbo.Sales", "dbo.Sales.extra", "dbo.[Sales]"],
)
def test_invalid_identifier_never_becomes_executable_sql(object_name: str) -> None:
    sql, parameters, supported = _metadata_verification_sql(object_name, "sql_server")

    assert supported is False
    assert sql == ""
    assert parameters == {}


def test_unsupported_engine_does_not_fall_back_to_mysql() -> None:
    check = _suggest_affected_object(_metadata("oracle"), _focus())

    assert check.status == "Unsupported"
    assert check.read_only is False
    assert check.verification_sql == ""


def test_exact_generated_sql_and_parameters_are_executed_unchanged() -> None:
    check = _suggest_affected_object(_metadata("sql_server"), _focus())

    class RecordingConnector:
        database_engine = DatabaseEngine.SQL_SERVER

        def __init__(self) -> None:
            self.call = None

        def execute_read_only_query(self, sql, limit=25, parameters=None):
            self.call = (sql, limit, parameters)
            return [{"COLUMN_NAME": "SaleId", "DATA_TYPE": "int"}]

    connector = RecordingConnector()
    result = execute_verification_check(
        connector=connector,
        claim=check.claim,
        verification_sql=check.verification_sql,
        expected_result=check.expected_result,
        source=check.source,
        verified_by="reviewer",
        parameters=check.parameters,
    )[0]

    assert result.status == "Verified"
    assert connector.call == (check.verification_sql, 25, check.parameters)
    assert result.verification_sql == check.verification_sql
