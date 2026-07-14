from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    RootCauseClaim,
    reason_about_evidence,
)
from legacydb_copilot.agents.recommendation_agent import recommend_actions
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.safe_sql_service import plan_safe_queries


def _metadata(include_diagnostics=True):
    parent = TableMetadata(
        "ops.orders",
        ["OrdersId", "BusinessKey", "Status", "CorrelationId"],
        10,
        ["OrdersId"],
        [],
        [],
    )
    child = TableMetadata(
        "ops.fulfillment_tasks",
        ["FulfillmentTasksId", "OrdersId", "BusinessKey", "Status", "CorrelationId"],
        20,
        ["FulfillmentTasksId"],
        [
            {
                "columns": ["OrdersId"],
                "referred_table": "ops.orders",
                "referred_columns": ["OrdersId"],
            }
        ],
        [],
    )
    diagnostic = TableMetadata(
        "ops.workflow_exceptions",
        ["BusinessKey", "Status", "Details", "CorrelationId"],
        1,
        [],
        [],
        [],
    )
    return MetadataSearchResult(
        [child, parent, *([diagnostic] if include_diagnostics else [])],
        [],
        [],
        "test",
        "sql_server",
    )


def _plan(
    question="Order ORD-42 is complete; why is the fulfillment task missing?",
    include_diagnostics=True,
):
    return plan_safe_queries(
        InvestigationIntent.MISSING_DATA,
        _metadata(include_diagnostics),
        extract_entities(question),
    )


def test_completed_upstream_transition_and_missing_downstream_are_proved_first():
    plan = _plan()

    assert plan[0].purpose == "Verify upstream entity and current transition status"
    assert "ops.orders" in plan[0].sql
    assert "BusinessKey = 'ORD-42'" in plan[0].sql
    assert "Status" in plan[0].sql
    assert plan[2].purpose == "Confirmed Missing Related Record Candidates"
    assert "LEFT JOIN ops.fulfillment_tasks" in plan[2].sql
    assert "c.FulfillmentTasksId IS NULL" in plan[2].sql


def test_failed_generation_inspects_exception_records_generically():
    plan = _plan()
    diagnostic = next(item for item in plan if "workflow exception" in item.purpose.lower())

    assert "ops.workflow_exceptions" in diagnostic.sql
    assert "CorrelationId" in diagnostic.sql
    assert "LIKE '%fulfillment%'" in diagnostic.sql
    assert "LIKE '%missing%'" in diagnostic.sql


def test_downstream_lookup_can_find_item_under_different_correlation_identifier():
    plan = _plan()
    lookup = next(item for item in plan if "alternate identifiers" in item.purpose)

    assert "JOIN ops.fulfillment_tasks" in lookup.sql
    assert "c.CorrelationId" in lookup.sql
    assert "p.BusinessKey = 'ORD-42'" in lookup.sql
    assert "c.BusinessKey" in lookup.sql


def test_duplicate_safe_replay_recommendation_is_conditional():
    reasoning = ReasoningResult(
        "Missing child confirmed",
        [RootCauseClaim("Expected downstream task was not generated")],
        [], [], [], [], [], [], [],
    )
    evidence = [
        CorrelatedEvidence(
            "SQL",
            "Confirmed Missing Related Record Candidates",
            "1 row(s) returned",
            "proof",
            "High",
        )
    ]

    recommendation = recommend_actions(
        intent=InvestigationIntent.MISSING_DATA,
        reasoning=reasoning,
        correlated_evidence=evidence,
    )
    text = " ".join(recommendation.immediate_fix + recommendation.permanent_fix).lower()

    assert "no child exists" in text
    assert "another correlation identifier" in text
    assert "idempot" in text
    assert "do not manually insert" in text


def test_insufficient_evidence_when_no_parent_child_relationship_exists():
    unrelated = MetadataSearchResult(
        [TableMetadata("ops.notes", ["NotesId", "Details"], 1, ["NotesId"], [], [])],
        [], [], "test", "sql_server",
    )
    plan = plan_safe_queries(
        InvestigationIntent.MISSING_DATA,
        unrelated,
        extract_entities("Order ORD-42 is complete; why is the fulfillment task missing?"),
    )

    assert all(item.purpose != "Confirmed Missing Related Record Candidates" for item in plan)
    assert all("alternate identifiers" not in item.purpose for item in plan)


def test_failed_generation_diagnostic_supports_confirmed_response_type():
    question = "Order ORD-42 is complete; why is the fulfillment task missing?"
    evidence = [
        EvidenceResult(
            "Verify upstream entity and current transition status",
            "SELECT BusinessKey, Status FROM ops.orders",
            [{"BusinessKey": "ORD-42", "Status": "Complete"}],
            evidence_id="SQL-1",
        ),
        EvidenceResult(
            "Confirmed Missing Related Record Candidates",
            "SELECT parent_reference, issue_type FROM ops.orders",
            [{"parent_reference": "ORD-42", "issue_type": "MISSING_RELATED_RECORD"}],
            evidence_id="SQL-2",
        ),
        EvidenceResult(
            "Inspect workflow exception evidence in ops.workflow_exceptions",
            "SELECT Details FROM ops.workflow_exceptions",
            [{"Status": "Open", "Details": "Downstream fulfillment creation failed"}],
            evidence_id="SQL-3",
        ),
    ]

    result = reason_about_evidence(
        question,
        IntentResult(InvestigationIntent.MISSING_DATA, 1.0, "test"),
        extract_entities(question),
        _metadata(),
        evidence,
        [],
    )

    assert result.response_type == "confirmed_root_cause"
    assert result.likely_root_causes[0].evidence_refs == ["SQL-1", "SQL-2", "SQL-3"]
    assert "transactional" in " ".join(result.recommended_fix).lower()
