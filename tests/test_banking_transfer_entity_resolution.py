import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_execution_service import execute_evidence_plan
from legacydb_copilot.services.evidence_focus_service import build_evidence_focus
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.safe_sql_service import PlannedQuery, plan_safe_queries
from legacydb_copilot.services.transfer_identifier_normalization import normalize_transfer_entities


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


def test_msg_wrapped_transfer_identifier_normalizes_to_typed_key() -> None:
    entities = extract_entities("Investigate transfer MSG-TRF-3101 for missing settlement")

    normalized, trace = normalize_transfer_entities(entities)
    identifiers = {
        item.value
        for item in normalized.entities
        if item.entity_type in {"business_identifier", "exact_id_or_code", "business_key"}
    }

    assert "TRF-3101" in identifiers
    assert trace.raw_extracted_entity == "MSG-TRF-3101"
    assert trace.normalized_entity == "TRF-3101"
    assert trace.normalization_rule_used == "msg_wrapped_transfer_key"


def test_lowercase_transfer_identifier_is_supported() -> None:
    entities = extract_entities("Investigate transfer trf-3101 for missing settlement")

    normalized, trace = normalize_transfer_entities(entities)
    identifiers = {
        item.value
        for item in normalized.entities
        if item.entity_type in {"business_identifier", "exact_id_or_code", "business_key"}
    }

    assert "TRF-3101" in identifiers
    assert trace.normalized_entity == "TRF-3101"


def test_invalid_msg_wrapped_identifier_does_not_normalize_to_transfer() -> None:
    entities = extract_entities("Investigate transfer MSG-TRF-ABC for missing settlement")

    normalized, trace = normalize_transfer_entities(entities)
    identifiers = {
        item.value
        for item in normalized.entities
        if item.entity_type in {"business_identifier", "exact_id_or_code", "business_key"}
    }

    assert "TRF-ABC" not in identifiers
    assert trace.normalized_entity is None


def test_unrelated_msg_identifier_does_not_normalize_to_transfer() -> None:
    entities = extract_entities("Investigate message MSG-9001 timeout in gateway")

    normalized, trace = normalize_transfer_entities(entities)
    identifiers = {
        item.value
        for item in normalized.entities
        if item.entity_type in {"business_identifier", "exact_id_or_code", "business_key"}
    }

    assert "TRF-9001" not in identifiers
    assert trace.normalized_entity is None


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


def test_msg_wrapped_transfer_primary_lookup_is_first_and_exact() -> None:
    metadata = _metadata()
    entities = extract_entities("Investigate transfer MSG-TRF-3101 completed without a matching balance movement")

    queries = plan_safe_queries(InvestigationIntent.PRODUCTION_INVESTIGATION, metadata, entities)

    assert queries
    assert queries[0].purpose == "Prove requested entity exists in eval.transfers"
    assert "FROM eval.transfers" in queries[0].sql
    assert "BusinessKey" in queries[0].sql
    assert "= 'TRF-3101'" in queries[0].sql


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


def test_msg_wrapped_transfer_keeps_transfers_primary_over_integration_messages() -> None:
    metadata = _metadata()
    question = "Investigate transfer MSG-TRF-3101 completed without a matching balance movement"
    entities = extract_entities(question)
    normalized_entities, _ = normalize_transfer_entities(entities)
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
        entities=normalized_entities,
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


def test_primary_transfer_lookup_survives_child_query_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = _metadata()
    entities = extract_entities("Investigate transfer TRF-3101 across accounts and transactions")

    original_validate = __import__(
        "legacydb_copilot.services.safe_sql_service",
        fromlist=["validate_read_only_sql"],
    ).validate_read_only_sql

    def reject_join_only(sql: str) -> None:
        if " join " in sql.lower():
            raise ValueError("Ambiguous join projection")
        original_validate(sql)

    monkeypatch.setattr(
        "legacydb_copilot.services.safe_sql_service.validate_read_only_sql",
        reject_join_only,
    )

    plan_statuses: list[dict] = []
    queries = plan_safe_queries(
        InvestigationIntent.PRODUCTION_INVESTIGATION,
        metadata,
        entities,
        debug_events=plan_statuses,
    )

    assert queries
    assert any("FROM eval.transfers" in query.sql and "BusinessKey" in query.sql for query in queries)
    assert any(item["status"] == "rejected" and "validator_rejected" in item["reason"] for item in plan_statuses)
    assert any(item["status"] == "validated" and "eval.transfers" in item["sql"] for item in plan_statuses)


def test_single_invalid_join_does_not_remove_valid_primary_query(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = _metadata()
    entities = extract_entities("Investigate transfer TRF-3101")

    original_supporting = __import__(
        "legacydb_copilot.services.safe_sql_service",
        fromlist=["_supporting_transfer_relationship_queries"],
    )._supporting_transfer_relationship_queries

    def supporting_with_invalid_join(md, ent, debug_events=None):
        return [
            PlannedQuery(
                purpose="Invalid child join",
                sql="SELECT * FROM eval.transfers t JOIN eval.accounts s ON s.account_id = t.account_id; DELETE FROM eval.accounts",
            ),
            *original_supporting(md, ent, debug_events=debug_events),
        ]

    monkeypatch.setattr(
        "legacydb_copilot.services.safe_sql_service._supporting_transfer_relationship_queries",
        supporting_with_invalid_join,
    )

    plan_statuses: list[dict] = []
    queries = plan_safe_queries(
        InvestigationIntent.PRODUCTION_INVESTIGATION,
        metadata,
        entities,
        debug_events=plan_statuses,
    )

    assert any("FROM eval.transfers" in query.sql and "BusinessKey" in query.sql for query in queries)
    assert any(item["status"] == "rejected" and "Invalid child join" in item["purpose"] for item in plan_statuses)
    assert any(item["status"] == "validated" and "Prove requested entity exists in eval.transfers" == item["purpose"] for item in plan_statuses)


def test_trf_primary_lookup_executes_and_returns_transfer_row() -> None:
    class FakeConnector:
        engine_type = "sql_server"

        def estimate_table_rows(self, _table_name: str) -> int:
            return 10

        def execute_read_only_query(self, sql: str, limit: int = 100):
            if "FROM eval.transfers" in sql and "TRF-3101" in sql:
                return [{"TransfersId": 3101, "BusinessKey": "TRF-3101", "Status": "Completed"}]
            return []

    evidence_statuses: list[dict] = []
    evidence = execute_evidence_plan(
        FakeConnector(),
        [
            PlannedQuery(
                purpose="Prove requested entity exists in eval.transfers",
                sql="SELECT TransfersId, BusinessKey, Status FROM eval.transfers WHERE CAST(BusinessKey AS NVARCHAR(MAX)) = 'TRF-3101'",
                query_id="Q-PRIMARY",
            )
        ],
        plan_statuses=evidence_statuses,
    )

    assert evidence and evidence[0].rows
    assert evidence[0].rows[0]["BusinessKey"] == "TRF-3101"
    assert any(item["status"] == "executed" and item["query_id"] == "Q-PRIMARY" for item in evidence_statuses)

