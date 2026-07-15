import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import detect_intent
from legacydb_copilot.agents.object_ranking_agent import rank_relevant_objects
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata


def table(name: str, columns: list[str], *, foreign_keys=None) -> TableMetadata:
    return TableMetadata(name, columns, 1, [columns[0]], foreign_keys or [], [])


@pytest.mark.parametrize("operational_name", [
    "transfer_exceptions", "order_integration_messages", "shipping_retry_queue",
    "payroll_batch_history", "clinic_workflow_events",
])
def test_discovers_operational_objects_across_schema_variations(operational_name: str) -> None:
    primary = table("business_records", ["record_id", "status", "updated_at"])
    operational = table(
        operational_name,
        ["event_id", "record_id", "status", "error_message", "created_at"],
        foreign_keys=[{"columns": ["record_id"], "referred_table": "business_records", "referred_columns": ["record_id"]}],
    )
    metadata = MetadataSearchResult([primary, operational], [], [], "test")
    entities = extract_entities("Why did record TRF-3101 fail during processing?")

    ranking = rank_relevant_objects(question="Why did record TRF-3101 fail during processing?", intent=detect_intent("Why did record TRF-3101 fail during processing?"), entities=entities, metadata=metadata)

    selected = {item.name: item for item in ranking.objects}
    assert operational_name in selected
    assert "operational" in selected[operational_name].reason.lower()


@pytest.mark.parametrize("internal_name", [
    "rag_document_chunks", "auth_users", "evaluation_runs", "framework_migrations", "approved_knowledge",
])
def test_excludes_unrelated_internal_tables(internal_name: str) -> None:
    primary = table("business_records", ["record_id", "status", "updated_at"])
    internal = table(internal_name, ["id", "record_id", "created_at"])
    metadata = MetadataSearchResult([primary, internal], [], [], "test")
    question = "Investigate business record TRF-3101"

    ranking = rank_relevant_objects(question=question, intent=detect_intent(question), entities=extract_entities(question), metadata=metadata)

    assert internal_name not in {item.name for item in ranking.objects}
    trace = next(item for item in ranking.metadata.candidate_trace if item.get("name") == internal_name)
    assert trace["decision"] == "rejected"
    assert "internal" in trace["rejection_reason"].lower()
