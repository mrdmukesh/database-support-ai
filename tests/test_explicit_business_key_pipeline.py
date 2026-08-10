from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.safe_sql_service import plan_safe_queries, validate_read_only_sql
from legacydb_copilot.services.transfer_identifier_normalization import (
    normalize_transfer_entities,
)


def _metadata(*tables: TableMetadata) -> MetadataSearchResult:
    return MetadataSearchResult(list(tables), [], [], "test", engine_type="sql_server")


def test_exact_identifier_probe_is_parameterized_and_planned_first() -> None:
    table = TableMetadata(
        "ops.WorkItems", ["WorkItemId", "ResultValue", "CreatedAt"], 100, ["WorkItemId"], [], []
    )
    queries = plan_safe_queries(
        InvestigationIntent.PRODUCTION_INVESTIGATION,
        _metadata(table),
        extract_entities("Why is ResultValue NULL for WorkItemId 2?"),
        resolved_entities=[
            {
                "resolved_table": "ops.WorkItems",
                "resolved_column": "WorkItemId",
                "identifier_value": 2,
            }
        ],
    )

    exact = queries[0]
    assert exact.row_scope == "exact_identifier"
    assert exact.entity_table == "ops.WorkItems"
    assert exact.identifier_column == "WorkItemId"
    assert exact.identifier_value == 2
    assert "WHERE WorkItemId = :resolved_identifier_1" in exact.sql
    assert exact.parameters == {"resolved_identifier_1": 2}
    assert " 2" not in exact.sql
    validate_read_only_sql(exact.sql)


def test_broad_rows_cannot_prove_an_explicit_identifier() -> None:
    entities, _ = normalize_transfer_entities(
        extract_entities("Why is ResultValue NULL for WorkItemId 2?")
    )
    gate = run_evidence_gate(
        question="Why is ResultValue NULL for WorkItemId 2?",
        intent=InvestigationIntent.PRODUCTION_INVESTIGATION,
        entities=entities,
        metadata=_metadata(TableMetadata("ops.WorkItems", ["WorkItemId", "ResultValue"], 10)),
        evidence=[
            EvidenceResult(
                "Broad candidate sample",
                "SELECT TOP 10 WorkItemId, ResultValue FROM ops.WorkItems",
                [{"WorkItemId": 1, "ResultValue": None}, {"WorkItemId": 2, "ResultValue": None}],
            )
        ],
        evidence_focus=None,
        documents=[],
    )

    assert gate.business_key_exists is False
    assert gate.reproduced is False


def test_one_row_exact_probe_proves_the_explicit_identifier() -> None:
    entities, _ = normalize_transfer_entities(
        extract_entities("Why is ResultValue NULL for WorkItemId 2?")
    )
    gate = run_evidence_gate(
        question="Why is ResultValue NULL for WorkItemId 2?",
        intent=InvestigationIntent.PRODUCTION_INVESTIGATION,
        entities=entities,
        metadata=_metadata(TableMetadata("ops.WorkItems", ["WorkItemId", "ResultValue"], 10)),
        evidence=[
            EvidenceResult(
                "Entity exact lookup in ops.WorkItems by WorkItemId",
                "SELECT WorkItemId, ResultValue FROM ops.WorkItems WHERE WorkItemId = :key",
                [{"WorkItemId": 2, "ResultValue": None}],
                parameters={"key": 2},
                exact_cardinality_result="ENTITY_RESOLVED",
                entity_table="ops.WorkItems",
                identifier_column="WorkItemId",
                identifier_value=2,
                row_scope="exact_identifier",
            )
        ],
        evidence_focus=None,
        documents=[],
    )

    assert gate.business_key_exists is True
