from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.agents.investigation_planner_agent import (
    RCA_INVESTIGATION_POLICY_VERSION,
    build_investigation_plan,
)
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata


def test_planner_records_generic_evidence_first_internal_plan() -> None:
    metadata = MetadataSearchResult(
        tables=[
            TableMetadata(
                name="app.People",
                columns=["PersonId", "DisplayName", "BirthDate"],
                score=0.9,
                primary_key=["PersonId"],
                foreign_keys=[],
                indexes=[{"name": "IX_People_DisplayName"}],
            )
        ],
        views=["app.PersonSummary"],
        procedures=["app.usp_ReadPerson"],
        version="test",
        engine_type="sql_server",
    )
    events: list[dict] = []

    queries = build_investigation_plan(
        InvestigationIntent.MISSING_DATA,
        metadata,
        extract_entities("Why is Jordan Lee's birth date NULL?"),
        events,
    )

    internal = next(
        event for event in events if event.get("event") == "internal_investigation_plan"
    )
    assert internal["policy_version"] == RCA_INVESTIGATION_POLICY_VERSION
    assert internal["candidate_entities"]
    assert internal["candidate_tables"][0]["name"] == "app.People"
    assert any(item["column"] == "BirthDate" for item in internal["affected_attribute_candidates"])
    assert (
        internal["candidate_procedures"][0]["requires_definition_or_dependency_verification"]
        is True
    )
    assert internal["verification_queries"] == [
        {"purpose": query.purpose, "sql": query.sql} for query in queries
    ]
    assert internal["ranking_order"][-1] == "semantic similarity"
    assert "Do not finalize" in internal["evidence_gate"]


def test_planner_policy_contains_no_scenario_specific_database_objects() -> None:
    assert RCA_INVESTIGATION_POLICY_VERSION == "evidence-first-generic-sqlserver-v1"
