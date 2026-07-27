from types import SimpleNamespace

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gap_detection_service import (
    EvidenceContradiction,
    EvidenceSourceType,
    GapQuestionType,
    GapStatus,
    detect_evidence_gaps,
)
from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult


def gate(
    *,
    reproduced: bool = True,
    business_key_exists: bool = True,
    relationship_exists: bool = True,
    expected_value: str = "Completed",
) -> EvidenceGateResult:
    return EvidenceGateResult(
        required=True,
        reproduced=reproduced,
        business_key_exists=business_key_exists,
        reported_condition_exists=reproduced,
        affected_rows_exist=True,
        parent_child_relationship_exists=relationship_exists,
        confirmed_facts=[],
        blocking_reasons=[],
        missing_evidence=[],
        status_interpretation=[],
        expected_value=expected_value,
    )


def runtime_evidence() -> EvidenceResult:
    return EvidenceResult(
        purpose="Inspect workflow runtime execution history and exceptions",
        sql="SELECT Status, Step FROM workflow_history WHERE EntityId = 1",
        rows=[
            {"Status": "Completed", "Step": "validated"},
            {"Status": "Failed", "Step": "delivery"},
        ],
        evidence_id="SQL-RUNTIME",
        execution_status="succeeded",
        evidence_semantics="positive_rows",
        supports_claim="Runtime workflow history and exception state were returned.",
        evidence_relevance="relevant",
    )


def procedure():
    return SimpleNamespace(
        definition_available=True,
        tables_written=["dbo.Target"],
    )


def gap_types(result) -> set[GapQuestionType]:
    return {item.question_type for item in result.gaps}


def test_missing_expected_state_rule_is_critical_gap() -> None:
    result = detect_evidence_gaps(
        evidence=[runtime_evidence()],
        evidence_gate=gate(expected_value=""),
        procedure_analysis=[procedure()],
    )
    gap = next(item for item in result.gaps if item.question_type is GapQuestionType.EXPECTED_STATE)
    assert gap.required_for_goal
    assert gap.recommended_next_evidence.evidence_type == "EXPECTED_STATE_RULE"


def test_procedure_metadata_does_not_prove_runtime_history() -> None:
    metadata = EvidenceResult(
        purpose="Inspect procedure definition",
        sql="",
        rows=[{"procedure_name": "dbo.Process"}],
        evidence_id="PROC-1",
        evidence_semantics="procedure_definition",
    )
    result = detect_evidence_gaps(
        evidence=[metadata],
        evidence_gate=gate(),
        procedure_analysis=[procedure()],
    )
    runtime_gap = next(
        item for item in result.gaps if item.question_type is GapQuestionType.RUNTIME_EXECUTION
    )
    assert "does not prove runtime execution" in runtime_gap.reason
    assert GapQuestionType.PROCEDURE_OWNERSHIP not in gap_types(result)


def test_failed_query_is_not_verified_absence() -> None:
    failed = EvidenceResult(
        purpose="Inspect runtime history",
        sql="SELECT Status FROM history WHERE EntityId = 1",
        rows=[],
        error="timeout",
        evidence_id="SQL-FAILED",
        execution_status="failed",
        evidence_semantics="execution_failure",
    )
    result = detect_evidence_gaps(evidence=[failed], evidence_gate=gate())
    gap = next(item for item in result.gaps if item.status is GapStatus.QUERY_FAILED)
    assert gap.supporting_evidence_refs == ("SQL-FAILED",)
    assert result.evidence_summary["verified_absence"] == 0


def test_blocked_query_is_not_verified_absence() -> None:
    blocked = EvidenceResult(
        purpose="Inspect runtime history",
        sql="SELECT Status FROM history",
        rows=[],
        error="scan policy",
        evidence_id="SQL-BLOCKED",
        execution_status="blocked",
        evidence_semantics="execution_failure",
    )
    result = detect_evidence_gaps(evidence=[blocked], evidence_gate=gate())
    gap = next(item for item in result.gaps if item.status is GapStatus.POLICY_BLOCKED)
    assert gap.supporting_evidence_refs == ("SQL-BLOCKED",)
    assert result.evidence_summary["verified_absence"] == 0


def test_contradictory_evidence_creates_critical_actual_state_gap() -> None:
    result = detect_evidence_gaps(
        evidence=[runtime_evidence()],
        evidence_gate=gate(),
        procedure_analysis=[procedure()],
        contradictions=[
            EvidenceContradiction(
                "The same entity has incompatible terminal states.",
                ("SQL-1", "SQL-2"),
            )
        ],
    )
    gap = next(item for item in result.gaps if item.status is GapStatus.CONTRADICTED)
    assert gap.question_type is GapQuestionType.ACTUAL_STATE
    assert gap.supporting_evidence_refs == ("SQL-1", "SQL-2")


def test_external_evidence_gap_is_distinct_from_database_gap() -> None:
    result = detect_evidence_gaps(
        evidence=[runtime_evidence()],
        evidence_gate=gate(),
        procedure_analysis=[procedure()],
        external_evidence_required=True,
    )
    gap = next(
        item for item in result.gaps if item.question_type is GapQuestionType.EXTERNAL_EVIDENCE
    )
    assert gap.source_type is EvidenceSourceType.EXTERNAL
    assert gap.status is GapStatus.BLOCKED_BY_MISSING_SOURCE


def test_fully_answered_question_has_no_gaps() -> None:
    result = detect_evidence_gaps(
        evidence=[runtime_evidence()],
        evidence_gate=gate(),
        procedure_analysis=[procedure()],
        expected_state_rule="Completed entities must have workflow history.",
        external_evidence_required=True,
        external_evidence_refs=["LOG-1"],
    )
    assert result.status == "COMPLETE"
    assert result.gaps == ()
    assert set(result.answered_questions) == set(GapQuestionType)
