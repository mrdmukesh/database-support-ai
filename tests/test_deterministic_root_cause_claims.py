from copy import deepcopy

import pytest

from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    RootCauseClaim,
    RootCauseSupportStatus,
    build_deterministic_root_cause_claim,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult


def evidence(evidence_id: str) -> EvidenceResult:
    return EvidenceResult("Inspect", "SELECT 1", [], evidence_id=evidence_id)


def test_valid_deterministic_conclusion_becomes_root_cause_claim() -> None:
    claim = build_deterministic_root_cause_claim("Deterministic cause", [], [])

    assert isinstance(claim, RootCauseClaim)
    assert claim.conclusion == "Deterministic cause"


def test_one_valid_deterministic_evidence_reference_produces_verified() -> None:
    claim = build_deterministic_root_cause_claim("Cause", ["SQL-1"], [evidence("SQL-1")])

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.VERIFIED


def test_multiple_valid_deterministic_evidence_references_produce_verified() -> None:
    claim = build_deterministic_root_cause_claim(
        "Cause", ["SQL-1", "SQL-2"], [evidence("SQL-1"), evidence("SQL-2")]
    )

    assert claim is not None
    assert claim.evidence_refs == ["SQL-1", "SQL-2"]
    assert claim.status is RootCauseSupportStatus.VERIFIED


def test_mixed_deterministic_evidence_references_produce_partially_supported() -> None:
    claim = build_deterministic_root_cause_claim("Cause", ["SQL-1", "SQL-2"], [evidence("SQL-1")])

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.PARTIALLY_SUPPORTED


def test_all_missing_deterministic_evidence_references_produce_unsupported() -> None:
    claim = build_deterministic_root_cause_claim("Cause", ["SQL-2", "SQL-3"], [evidence("SQL-1")])

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.UNSUPPORTED


def test_empty_deterministic_evidence_references_produce_not_evaluated() -> None:
    claim = build_deterministic_root_cause_claim("Cause", [], [evidence("SQL-1")])

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.NOT_EVALUATED


@pytest.mark.parametrize("conclusion", ["", "   ", None])
def test_blank_deterministic_conclusion_is_rejected(conclusion) -> None:
    assert build_deterministic_root_cause_claim(conclusion, [], []) is None


@pytest.mark.parametrize("malformed_refs", [{"id": "SQL-1"}, 42, ["SQL-1", {"id": "SQL-2"}, None]])
def test_malformed_deterministic_evidence_references_do_not_crash(malformed_refs) -> None:
    claim = build_deterministic_root_cause_claim("Cause", malformed_refs, [evidence("SQL-1")])

    assert claim is not None


def test_duplicate_valid_deterministic_references_still_produce_verified() -> None:
    claim = build_deterministic_root_cause_claim("Cause", ["SQL-1", "SQL-1"], [evidence("SQL-1")])

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.VERIFIED


def test_deterministic_claim_inputs_are_not_mutated() -> None:
    conclusion = " Cause "
    references = [" SQL-1 ", ""]
    original_references = deepcopy(references)

    claim = build_deterministic_root_cause_claim(conclusion, references, [evidence("SQL-1")])

    assert conclusion == " Cause "
    assert references == original_references
    assert claim is not None
    assert claim.conclusion == "Cause"
    assert claim.evidence_refs == ["SQL-1"]


def test_procedure_names_are_not_automatically_treated_as_evidence_ids() -> None:
    claim = build_deterministic_root_cause_claim("Cause mentions retry_claims", ["retry_claims"], [evidence("SQL-1")])

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.UNSUPPORTED


def test_metadata_descriptions_are_not_automatically_treated_as_evidence_ids() -> None:
    claim = build_deterministic_root_cause_claim(
        "Cause", ["claims table has a parent relationship"], [evidence("SQL-1")]
    )

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.UNSUPPORTED


def test_existing_deterministic_reasoning_result_output_remains_display_compatible() -> None:
    result = ReasoningResult(
        summary="Summary",
        likely_root_causes=["Existing deterministic cause"],
        supporting_evidence=[],
        missing_evidence=[],
        recommended_fix=[],
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=[],
    )

    assert result.likely_root_causes == ["Existing deterministic cause"]
    assert all(isinstance(item, RootCauseClaim) for item in result.likely_root_causes)
    assert [str(item) for item in result.likely_root_causes] == ["Existing deterministic cause"]
