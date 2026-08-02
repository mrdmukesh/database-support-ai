from legacydb_copilot.agents.entity_extraction_agent import (
    EntityExtractionResult,
    ExtractedEntity,
)
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchResult,
    TableMetadata,
)
from legacydb_copilot.services.safe_sql_service import plan_safe_queries


def test_resolved_identifier_builds_minimal_native_parameterized_lookup() -> None:
    metadata = MetadataSearchResult(
        tables=[
            TableMetadata(
                "ops.Subject",
                ["SubjectId", "SubjectNumber", "BusinessKey", "RequiredInput", "Notes"],
                1.0,
                primary_key=["SubjectId"],
                column_types={
                    "SubjectId": "int",
                    "SubjectNumber": "nvarchar",
                    "RequiredInput": "date",
                },
            )
        ],
        views=[],
        procedures=[],
        version="test",
        engine_type="sql_server",
    )
    entities = EntityExtractionResult(
        entities=[ExtractedEntity("business_identifier", "SUB-2042")],
        suspected_issue="RequiredInput is missing for the derived calculation",
        likely_module=None,
        business_keywords=["RequiredInput"],
    )

    queries = plan_safe_queries(
        InvestigationIntent.PRODUCTION_INVESTIGATION,
        metadata,
        entities,
        provider="sql_server",
        resolved_entities=[
            {
                "resolved_table": "ops.Subject",
                "resolved_column": "SubjectNumber",
                "matched_value": "SUB-2042",
            }
        ],
    )

    lookup = queries[0]
    assert lookup.sql == (
        "SELECT SubjectId, SubjectNumber, RequiredInput FROM ops.Subject "
        "WHERE SubjectNumber = 'SUB-2042'"
    )
    assert lookup.execution_sql.endswith("WHERE SubjectNumber = :investigation_value_1")
    assert lookup.parameters == {"investigation_value_1": "SUB-2042"}
    assert "CAST(" not in lookup.sql
    assert " OR " not in lookup.sql
    assert "TOP" not in lookup.sql
    assert all(item.purpose != "Inspect relevant rows in ops.Subject" for item in queries)
