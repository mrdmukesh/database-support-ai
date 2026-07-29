from __future__ import annotations

import pytest

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import reason_about_evidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.reasoning_dispatch_service import (
    ReasoningMode,
    ReasoningPermission,
    dispatch_reasoning,
)
from legacydb_copilot.services.verified_evidence_service import (
    normalize_verified_evidence,
)


def _reason(
    evidence: list[EvidenceResult],
    question: str = "Explain whether the requested calculation has sufficient source data.",
):
    return reason_about_evidence(
        question=question,
        intent=IntentResult(
            InvestigationIntent.GENERAL_DATABASE_QUESTION,
            0.9,
            "generic nullable-field investigation",
        ),
        entities=EntityExtractionResult(
            entities=[],
            suspected_issue="calculation unavailable",
            likely_module="records",
        ),
        metadata=MetadataSearchResult([], [], [], "test"),
        evidence=evidence,
        documents=[],
    )


def test_verified_null_is_evidence_not_absence_failure_or_root_cause() -> None:
    evidence = [
        EvidenceResult(
            purpose="Verify requested record and nullable calculation input",
            sql="SELECT RecordKey, BirthDate FROM PersonRecord WHERE RecordKey = :key",
            rows=[{"RecordKey": "REC-42", "BirthDate": None}],
            evidence_id="SQL-1",
            evidence_semantics="null_value",
            evidence_relevance="relevant",
            supports_claim="The selected row has a NULL BirthDate.",
        )
    ]

    normalized = normalize_verified_evidence(evidence)
    response = _reason(evidence, "Why can the age not be calculated?")

    assert normalized.verified_evidence_count == 1
    assert normalized.evidence_categories == ["null_value_rows"]
    assert normalized.evidence_gaps == []
    assert response.response_type == "inconclusive_verified_null"
    assert "age calculation cannot be completed" in response.summary
    assert "Evidence gap:" in response.summary
    assert response.likely_root_causes == []
    assert any(
        "BirthDate is NULL" in item and "SQL-1" in item
        for item in response.supporting_evidence
    )
    assert any("does not establish its origin" in item for item in response.missing_evidence)
    assert any(
        "prerequisite" in item and "No change has been executed" in item
        for item in response.recommended_fix
    )
    assert all(
        "employee not found" not in str(item).casefold()
        for item in response.supporting_evidence
    )
    assert all("executed successfully" not in item.casefold() for item in response.proof_of_fix)


def test_valid_nullable_field_is_positive_evidence_without_null_conclusion() -> None:
    evidence = [
        EvidenceResult(
            purpose="Verify requested record and calculation input",
            sql="SELECT RecordKey, BirthDate FROM PersonRecord WHERE RecordKey = :key",
            rows=[{"RecordKey": "REC-43", "BirthDate": "1990-05-06"}],
            evidence_id="SQL-2",
            evidence_semantics="positive_rows",
            evidence_relevance="relevant",
            supports_claim="The selected row has a populated BirthDate.",
        )
    ]

    normalized = normalize_verified_evidence(evidence)
    response = _reason(evidence)

    assert normalized.evidence_categories == ["positive_sql_rows"]
    assert response.response_type != "inconclusive_verified_null"
    assert "NULL source values" not in response.summary
    assert not any("prerequisite" in item for item in response.recommended_fix)


def test_missing_row_is_not_null_evidence_and_does_not_invent_a_cause() -> None:
    evidence = [
        EvidenceResult(
            purpose="Verify requested record",
            sql="SELECT RecordKey, BirthDate FROM PersonRecord WHERE RecordKey = :key",
            rows=[],
            evidence_id="SQL-3",
            evidence_semantics="not_applicable",
            evidence_relevance="relevant",
        )
    ]

    normalized = normalize_verified_evidence(evidence)
    response = _reason(evidence)

    assert normalized.verified_evidence_count == 0
    assert "null_value_rows" not in normalized.evidence_categories
    assert response.response_type != "inconclusive_verified_null"
    assert all("is NULL" not in item for item in response.supporting_evidence)
    assert all(claim.status.value != "VERIFIED" for claim in response.likely_root_causes)


@pytest.mark.parametrize(
    "verified_count,reproduced,condition,permission,mode,invoke",
    [
        (0, False, False, ReasoningPermission.DENY_REASONING, ReasoningMode.SKIP, False),
        (1, True, True, ReasoningPermission.ALLOW_REASONING, ReasoningMode.NORMAL_ROOT_CAUSE, True),
        (
            1,
            False,
            False,
            ReasoningPermission.ALLOW_REASONING,
            ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
            True,
        ),
    ],
)
def test_dispatch_depends_on_verified_evidence_state(
    verified_count,
    reproduced,
    condition,
    permission,
    mode,
    invoke,
) -> None:
    from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult

    gate = EvidenceGateResult(
        required=True,
        reproduced=reproduced,
        business_key_exists=verified_count > 0,
        reported_condition_exists=condition,
        affected_rows_exist=verified_count > 0,
        parent_child_relationship_exists=True,
        confirmed_facts=[],
        blocking_reasons=[],
        missing_evidence=[],
        status_interpretation=[],
        verified_evidence=verified_count > 0,
        verified_evidence_count=verified_count,
    )

    decision = dispatch_reasoning(gate)

    assert decision.permission == permission
    assert decision.mode == mode
    assert decision.invoke_llm is invoke
    if not invoke:
        assert decision.reason_code == "NO_VERIFIED_EVIDENCE"
