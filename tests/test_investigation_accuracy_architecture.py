from types import SimpleNamespace

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    RootCauseClaim,
    RootCauseSupportStatus,
    finalize_evidence_backed_response_type,
    reason_about_evidence,
)
from legacydb_copilot.agents.report_composer_agent import _evidence_only_summary
from legacydb_copilot.routers.chat import _evidence_to_json, _expand_related_id_evidence
from legacydb_copilot.services.claim_verification_service import (
    EvidenceReference,
    parse_structured_claim,
    verify_claim,
)
from legacydb_copilot.services.confidence_scoring_service import score_confidence
from legacydb_copilot.services.evidence_correlation_service import correlate_evidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchResult,
    TableMetadata,
)


def _evidence(evidence_id: str, rows: list[dict], **overrides) -> EvidenceResult:
    values = {
        "evidence_id": evidence_id,
        "evidence_semantics": "positive_rows",
        "supports_claim": "Verified result.",
        "evidence_relevance": "relevant",
    }
    values.update(overrides)
    return EvidenceResult("Inspect entity", "SELECT value FROM Entity", rows, **values)


def test_persisted_evidence_preserves_every_bounded_row() -> None:
    import json

    rows = [{"value": index} for index in range(15)]
    payload = json.loads(_evidence_to_json([_evidence("SQL-1", rows)]))[0]

    assert payload["rows"] == rows
    assert payload["sample_rows"] == rows[:10]
    assert payload["rows_truncated"] is False
    assert payload["evidence_relevance"] == "relevant"


def test_evidence_only_summary_does_not_drop_later_evidence() -> None:
    bundle = SimpleNamespace(
        evidence=[_evidence(f"SQL-{index}", [{"value": index}]) for index in range(1, 9)],
        procedure_analysis=[],
    )

    summary = _evidence_only_summary(bundle)

    assert "8 row(s)" not in summary
    assert summary.count("Inspect entity returned 1 row(s)") == 8


def test_unverified_empty_result_is_not_correlated_as_absence() -> None:
    result = _evidence(
        "SQL-1",
        [],
        evidence_semantics="not_applicable",
        supports_claim="",
        evidence_relevance="unverified",
    )

    correlated = correlate_evidence(evidence=[result], procedure_analysis=[], documents=[])

    assert correlated[0].confidence == "Low"
    assert "not verified" in correlated[0].finding


def test_confidence_does_not_reward_irrelevant_rows_or_unverified_absence() -> None:
    metadata = MetadataSearchResult([], [], [], "test")
    irrelevant = _evidence(
        "SQL-1", [{"value": "x"}], supports_claim="", evidence_relevance="irrelevant"
    )
    unverified_empty = _evidence(
        "SQL-2",
        [],
        evidence_semantics="not_applicable",
        supports_claim="",
        evidence_relevance="unverified",
    )

    assert score_confidence(metadata, [irrelevant, unverified_empty], []) == 0.2


def test_claim_cannot_ignore_conflicting_uncited_collected_evidence() -> None:
    refs = [
        EvidenceReference(
            evidence_id="SQL-1",
            type="SQL_RESULT",
            title="First read",
            columns=("Status",),
            rows=({"Status": "Ready"},),
            row_count=1,
        ),
        EvidenceReference(
            evidence_id="SQL-2",
            type="SQL_RESULT",
            title="Second read",
            columns=("Status",),
            rows=({"Status": "Blocked"},),
            row_count=1,
        ),
    ]
    claim = parse_structured_claim({"statement": "Status is Ready.", "evidence_ids": ["SQL-1"]})
    assert claim is not None

    result = verify_claim(claim, refs)

    assert result.verification_result == "REJECTED"
    assert result.rejection_code == "CONTRADICTORY_EVIDENCE"
    assert result.contradictory_evidence_ids == ("SQL-2",)


def _base_reasoning(*, claims=None, response_type="inconclusive_verified_null"):
    return ReasoningResult(
        summary="Evidence summary.",
        likely_root_causes=list(claims or []),
        supporting_evidence=[],
        missing_evidence=[],
        recommended_fix=[],
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=[],
        response_type=response_type,
    )


def test_banking_retry_shape_ignores_unrelated_null_and_confirms_verified_cause() -> None:
    evidence = [
        _evidence(
            "SQL-1",
            [{"BusinessKey": "TRANSFER-10", "RetryStatus": "Failed", "Notes": None}],
            evidence_semantics="null_value",
        ),
        EvidenceResult(
            "Inspect retry exceptions",
            "SELECT Status, ErrorMessage FROM RetryExceptions",
            [{"Status": "Failed", "ErrorMessage": "Retry limit reached"}],
            evidence_id="SQL-2",
            evidence_semantics="positive_rows",
            supports_claim="The retry exception records the failed condition.",
            evidence_relevance="relevant",
        ),
    ]
    deterministic = reason_about_evidence(
        question="Investigate why the transfer retry failed after repeated attempts.",
        intent=IntentResult(InvestigationIntent.PROCESS_FLOW_BREAK, 1.0, "retry"),
        entities=EntityExtractionResult([], "retry failed", "banking"),
        metadata=MetadataSearchResult([], [], [], "test"),
        evidence=evidence,
        documents=[],
    )
    verified = RootCauseClaim(
        "The retry failure is verified.",
        ["SQL-1"],
        RootCauseSupportStatus.VERIFIED,
    )

    final = finalize_evidence_backed_response_type(
        _base_reasoning(claims=[verified], response_type=deterministic.response_type),
        reproduced=True,
        evidence_required=True,
    )

    assert deterministic.response_type != "inconclusive_verified_null"
    assert deterministic.likely_root_causes[0].status is RootCauseSupportStatus.VERIFIED
    assert "Retry limit reached" in deterministic.likely_root_causes[0].conclusion
    assert final.response_type == "confirmed_root_cause"


def test_payroll_retry_shape_caps_rejected_insufficient_cause() -> None:
    reasoning = finalize_evidence_backed_response_type(
        _base_reasoning(),
        reproduced=True,
        evidence_required=True,
        rejected_claim_count=1,
    )

    confidence = score_confidence(
        MetadataSearchResult([], [], [], "test"),
        [_evidence("SQL-1", [{"Status": "Failed", "OptionalNote": None}])],
        [],
        reasoning=reasoning,
        rejected_claim_count=1,
    )

    assert reasoning.response_type == "insufficient_evidence"
    assert confidence <= 0.35


def test_causal_evidence_obligation_is_independent_of_generic_intent() -> None:
    gate = run_evidence_gate(
        question="Investigate why retry processing failed.",
        intent=InvestigationIntent.GENERAL_DATABASE_QUESTION,
        entities=EntityExtractionResult([], "retry failed", "records"),
        metadata=MetadataSearchResult([], [], [], "test"),
        evidence=[],
        evidence_focus=None,
        documents=[],
    )

    assert gate.required is True
    assert gate.reproduced is False


def test_related_id_expansion_uses_central_scan_policy_audit() -> None:
    class Connector:
        def execute_read_only_query(self, sql, limit=25):
            return [{"CorrelationId": "CORR-10", "Status": "Failed"}]

    metadata = MetadataSearchResult(
        [TableMetadata("eval.retry_events", ["CorrelationId", "Status"], 5)],
        [],
        [],
        "test",
        engine_type="sql_server",
    )
    evidence = [
        _evidence("SQL-1", [{"BusinessKey": "PAY-10", "CorrelationId": "CORR-10"}])
    ]

    related = _expand_related_id_evidence(Connector(), metadata, evidence)

    assert related
    audit = related[0].scan_policy_decision
    assert audit["audit_state"] == "audited"
    assert audit["policy_applied"]
    assert audit["decision"] == "allowed"
    assert audit["reason"]
    assert audit["original_sql_reference"]
    assert audit["executed_sql_reference"]
    assert audit["execution_status"] == "succeeded"
    assert audit["row_expansion_context"]["source"] == "related_id_expansion"
