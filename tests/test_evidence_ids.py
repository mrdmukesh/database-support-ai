import json
from dataclasses import asdict

from legacydb_copilot.routers.chat import _evidence_to_json
from legacydb_copilot.services.evidence_execution_service import (
    EvidenceResult,
    execute_evidence_plan,
)
from legacydb_copilot.services.safe_sql_service import PlannedQuery


class FakeConnector:
    database_engine = "sqlite"

    def execute_read_only_query(self, sql: str, limit: int = 100):
        return [{"value": sql}]


def test_evidence_result_has_non_empty_unique_ids() -> None:
    first = EvidenceResult("First", "SELECT 1", [])
    second = EvidenceResult("Second", "SELECT 2", [])

    assert first.evidence_id
    assert second.evidence_id
    assert first.evidence_id != second.evidence_id


def test_evidence_serialization_includes_evidence_id() -> None:
    evidence = EvidenceResult("Inspect", "SELECT 1", [], evidence_id="SQL-1")

    assert asdict(evidence)["evidence_id"] == "SQL-1"
    assert json.loads(_evidence_to_json([evidence]))[0]["evidence_id"] == "SQL-1"


def test_persisted_evidence_preserves_exact_entity_scope() -> None:
    evidence = EvidenceResult(
        purpose="authoritative source proof",
        sql="SELECT AssetCode, RequiredInput FROM ops.Asset WHERE AssetCode = :key",
        rows=[{"AssetCode": "AST-2042", "RequiredInput": None}],
        entity_table="ops.Asset",
        identifier_column="AssetCode",
        identifier_value="AST-2042",
        row_scope="exact_entity",
    )

    persisted = json.loads(_evidence_to_json([evidence]))[0]

    assert persisted["entity_table"] == "ops.Asset"
    assert persisted["identifier_column"] == "AssetCode"
    assert persisted["identifier_value"] == "AST-2042"
    assert persisted["row_scope"] == "exact_entity"


def test_execute_evidence_plan_assigns_consistent_investigation_ids() -> None:
    result = execute_evidence_plan(
        FakeConnector(),
        [PlannedQuery("First", "SELECT 1"), PlannedQuery("Second", "SELECT 2")],
    )

    assert [item.evidence_id for item in result] == ["SQL-1", "SQL-2"]
