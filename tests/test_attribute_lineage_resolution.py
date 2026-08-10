from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.agents.investigation_planner_agent import build_investigation_plan
from legacydb_copilot.services.attribute_lineage_service import resolve_attribute_lineage
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import build_evidence_focus
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.stored_procedure_intelligence import analyze_stored_procedures


class DefinitionConnector:
    def __init__(self, definitions: dict[str, str]):
        self.definitions = definitions

    def get_procedure_definition(self, name: str) -> str:
        return self.definitions[name]


def metadata(columns: list[str] | None = None) -> MetadataSearchResult:
    return MetadataSearchResult(
        [TableMetadata("ops.WorkItems", columns or ["WorkItemId", "SourceValue"], 10)],
        [],
        ["ops.usp_ResultValue", "ops.usp_Summary"],
        "test",
        engine_type="sql_server",
    )


def resolved() -> list[dict]:
    return [
        {
            "resolved_table": "ops.WorkItems",
            "resolved_column": "WorkItemId",
            "identifier_value": 2,
        }
    ]


def analyses():
    return analyze_stored_procedures(
        DefinitionConnector(
            {
                "ops.usp_ResultValue": """
                    CREATE PROCEDURE ops.usp_ResultValue @WorkItemId int AS
                    SELECT CASE WHEN w.SourceValue IS NULL THEN NULL
                                ELSE w.SourceValue END AS ResultValue
                    FROM ops.WorkItems w WHERE w.WorkItemId = @WorkItemId
                """,
                "ops.usp_Summary": """
                    CREATE PROCEDURE ops.usp_Summary @WorkItemId int AS
                    SELECT w.WorkItemId, COUNT(*) AS ItemCount
                    FROM ops.WorkItems w WHERE w.WorkItemId = @WorkItemId
                    GROUP BY w.WorkItemId
                """,
            }
        ),
        ["ops.usp_ResultValue", "ops.usp_Summary"],
    )


def test_derived_attribute_extracts_definition_sources_and_exact_query() -> None:
    entities = extract_entities("Why is ResultValue NULL for WorkItemId 2?")
    candidates, queries = resolve_attribute_lineage(
        entities=entities,
        metadata=metadata(),
        procedures=analyses(),
        resolved_entities=resolved(),
    )

    selected = next(item for item in candidates if item.selected)
    assert selected.producer == "ops.usp_ResultValue"
    assert selected.source_columns == ("SourceValue",)
    assert "CASE" in selected.expression.upper()
    assert queries[0].parameters == {"attribute_entity_value": 2}
    assert queries[0].sql.endswith("WHERE WorkItemId = :attribute_entity_value")
    assert "SourceValue" in queries[0].sql


def test_stored_attribute_resolves_as_direct_catalog_column() -> None:
    candidates, queries = resolve_attribute_lineage(
        entities=extract_entities("Why is StoredValue NULL for WorkItemId 2?"),
        metadata=metadata(["WorkItemId", "StoredValue"]),
        procedures=[],
        resolved_entities=resolved(),
    )

    assert candidates[0].producer_type == "STORED_COLUMN"
    assert candidates[0].source_columns == ("StoredValue",)
    assert "StoredValue" in queries[0].sql


def test_definition_dependency_outranks_table_overlap_and_name_similarity() -> None:
    entities = extract_entities("Why is ResultValue NULL for WorkItemId 2?")
    procedures = analyses()
    candidates, _ = resolve_attribute_lineage(
        entities=entities,
        metadata=metadata(),
        procedures=procedures,
        resolved_entities=resolved(),
    )
    evidence = [
        EvidenceResult(
            "Entity exact lookup in ops.WorkItems by WorkItemId",
            "SELECT WorkItemId, SourceValue FROM ops.WorkItems WHERE WorkItemId = :key",
            [{"WorkItemId": 2, "SourceValue": None}],
            parameters={"key": 2},
            exact_cardinality_result="ENTITY_RESOLVED",
            entity_table="ops.WorkItems",
            identifier_column="WorkItemId",
            identifier_value=2,
            row_scope="exact_identifier",
        )
    ]

    focus = build_evidence_focus(
        question="Why is ResultValue NULL for WorkItemId 2?",
        intent=InvestigationIntent.PRODUCTION_INVESTIGATION,
        entities=entities,
        metadata=metadata(),
        evidence=evidence,
        correlated_evidence=[],
        procedure_analysis=procedures,
        documents=[],
        attribute_lineage=candidates,
    )

    assert focus.ranked_procedures[0].procedure == "ops.usp_ResultValue"
    assert "produces affected attribute" in " ".join(
        focus.ranked_procedures[0].evidence_found
    )


def test_attribute_lineage_query_precedes_broad_fallback_queries() -> None:
    entities = extract_entities("Why is ResultValue NULL for WorkItemId 2?")
    candidates, lineage_queries = resolve_attribute_lineage(
        entities=entities,
        metadata=metadata(),
        procedures=analyses(),
        resolved_entities=resolved(),
    )
    plan = build_investigation_plan(
        InvestigationIntent.PRODUCTION_INVESTIGATION,
        metadata(),
        entities,
        resolved_entities=resolved(),
        attribute_lineage_queries=lineage_queries,
    )

    assert plan[0].purpose.startswith("Entity exact lookup")
    assert plan[1].purpose.startswith("Verify attribute lineage inputs")
    assert any("prove reported condition" in item.purpose.casefold() for item in plan[2:])
    assert candidates[0].selected
    assert all(
        item.rejection_reason for item in candidates if not item.selected
    )
