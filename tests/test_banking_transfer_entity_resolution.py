import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import build_evidence_focus
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.safe_sql_service import plan_safe_queries


def _metadata() -> MetadataSearchResult:
    transfers = TableMetadata(
        "eval.transfers",
        ["transfer_id", "BusinessKey", "account_id", "Status", "created_at"],
        8,
        ["transfer_id"],
        foreign_keys=[
            {
                "columns": ["account_id"],
                "referred_table": "eval.accounts",
                "referred_columns": ["account_id"],
            }
        ],
        indexes=[],
    )
    accounts = TableMetadata(
        "eval.accounts",
        ["account_id", "account_number", "account_status"],
        7,
        ["account_id"],
        foreign_keys=[],
        indexes=[],
    )

    def child(name: str, child_id: str) -> TableMetadata:
        return TableMetadata(
            name,
            [child_id, "transfer_id", "Status", "created_at"],
            6,
            [child_id],
            foreign_keys=[
                {
                    "columns": ["transfer_id"],
                    "referred_table": "eval.transfers",
                    "referred_columns": ["transfer_id"],
                }
            ],
            indexes=[],
        )

    integration = TableMetadata(
        "eval.integration_messages",
        ["message_id", "transfer_id", "BusinessKey", "message", "created_at"],
        12,
        ["message_id"],
        foreign_keys=[
            {
                "columns": ["transfer_id"],
                "referred_table": "eval.transfers",
                "referred_columns": ["transfer_id"],
            }
        ],
        indexes=[],
    )
    return MetadataSearchResult(
        tables=[
            integration,
            transfers,
            accounts,
            child("eval.transactions", "transaction_id"),
            child("eval.fraud_alerts", "alert_id"),
            child("eval.audit_history", "audit_id"),
            child("eval.payment_instructions", "instruction_id"),
            child("eval.settlement_records", "settlement_id"),
        ],
        views=[],
        procedures=[],
        version="test",
        engine_type="sql_server",
    )


def test_extracts_typed_transfer_identifier_exactly() -> None:
    entities = extract_entities(
        "Investigate transfer TRF-3101 completed without a matching balance movement"
    )
    identifiers = {
        item.value
        for item in entities.entities
        if item.entity_type in {"business_identifier", "exact_id_or_code"}
    }

    assert "TRF-3101" in identifiers


def test_transfer_primary_lookup_is_first_and_exact() -> None:
    metadata = _metadata()
    entities = extract_entities(
        "Investigate transfer TRF-3101 completed without a matching balance movement"
    )

    queries = plan_safe_queries(InvestigationIntent.PRODUCTION_INVESTIGATION, metadata, entities)

    assert queries
    assert queries[0].purpose == "Prove requested entity exists in eval.transfers"
    assert "FROM eval.transfers" in queries[0].sql
    assert "BusinessKey" in queries[0].sql
    assert "= 'TRF-3101'" in queries[0].sql
    assert "COMPLETED" not in queries[0].sql.upper()


def test_transfer_relationship_queries_include_supporting_objects_and_keep_integration_supporting() -> None:
    metadata = _metadata()
    entities = extract_entities("Investigate transfer TRF-3101 completed without a matching balance movement")

    queries = plan_safe_queries(InvestigationIntent.PRODUCTION_INVESTIGATION, metadata, entities)
    sql_by_purpose = {query.purpose: query.sql for query in queries}

    assert any("eval.accounts" in sql for sql in sql_by_purpose.values())
    assert any("eval.transactions" in sql for sql in sql_by_purpose.values())
    assert any("eval.fraud_alerts" in sql for sql in sql_by_purpose.values())
    assert any("eval.audit_history" in sql for sql in sql_by_purpose.values())
    assert any("eval.payment_instructions" in sql for sql in sql_by_purpose.values())
    assert any("eval.settlement_records" in sql for sql in sql_by_purpose.values())
    integration_purpose = next(purpose for purpose, sql in sql_by_purpose.items() if "eval.integration_messages" in sql)
    assert "support" in integration_purpose.lower()


def test_transfer_focus_remains_primary_over_integration_messages() -> None:
    metadata = _metadata()
    question = "Investigate transfer TRF-3101 completed without a matching balance movement"
    evidence = [
        EvidenceResult(
            "Prove requested entity exists in eval.transfers",
            "SELECT transfer_id, BusinessKey, Status FROM eval.transfers WHERE BusinessKey = 'TRF-3101'",
            [{"transfer_id": 3101, "BusinessKey": "TRF-3101", "Status": "Completed"}],
        ),
        EvidenceResult(
            "Inspect diagnostic support relationship evidence in eval.integration_messages",
            "SELECT message_id, transfer_id, message FROM eval.transfers t JOIN eval.integration_messages s ON s.transfer_id = t.transfer_id WHERE t.BusinessKey = 'TRF-3101'",
            [
                {"message_id": 1, "transfer_id": 3101, "message": "settlement lag"},
                {"message_id": 2, "transfer_id": 3101, "message": "retry ack delayed"},
            ],
        ),
    ]

    focus = build_evidence_focus(
        question=question,
        intent=InvestigationIntent.PRODUCTION_INVESTIGATION,
        entities=extract_entities(question),
        metadata=metadata,
        evidence=evidence,
        correlated_evidence=[],
        procedure_analysis=[],
        documents=[],
    )

    assert focus.affected_object == "eval.transfers"
    assert focus.inferred_business_key == "TRF-3101"
    assert focus.selected_business_key_value == "TRF-3101"


def test_transfer_evidence_gate_fails_with_precise_reason_when_key_not_found() -> None:
    metadata = _metadata()
    question = "Investigate transfer TRF-3101 completed without a matching balance movement"
    entities = extract_entities(question)
    evidence = [
        EvidenceResult(
            "Prove requested entity exists in eval.transfers",
            "SELECT transfer_id, BusinessKey, Status FROM eval.transfers WHERE BusinessKey = 'TRF-3101'",
            [],
        )
    ]

    focus = build_evidence_focus(
        question=question,
        intent=InvestigationIntent.PRODUCTION_INVESTIGATION,
        entities=entities,
        metadata=metadata,
        evidence=evidence,
        correlated_evidence=[],
        procedure_analysis=[],
        documents=[],
    )
    gate = run_evidence_gate(
        question=question,
        intent=InvestigationIntent.PRODUCTION_INVESTIGATION,
        entities=entities,
        metadata=metadata,
        evidence=evidence,
        evidence_focus=focus,
        documents=[],
    )

    assert not gate.reproduced
    assert any("Supplied business key not found" in reason for reason in gate.blocking_reasons)

