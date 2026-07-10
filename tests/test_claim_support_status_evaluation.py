from dataclasses import asdict
import json

from legacydb_copilot.agents.reasoning_agent import (
    RootCauseClaim,
    RootCauseSupportStatus,
    evaluate_claim_support_status,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult


def evidence(evidence_id: str) -> EvidenceResult:
    return EvidenceResult("Inspect", "SELECT 1", [], evidence_id=evidence_id)


def test_empty_evidence_refs_returns_not_evaluated() -> None:
    evaluated = evaluate_claim_support_status(RootCauseClaim("Cause"), [evidence("SQL-1")])

    assert evaluated.status is RootCauseSupportStatus.NOT_EVALUATED


def test_one_valid_evidence_reference_returns_verified() -> None:
    evaluated = evaluate_claim_support_status(RootCauseClaim("Cause", ["SQL-1"]), [evidence("SQL-1")])

    assert evaluated.status is RootCauseSupportStatus.VERIFIED


def test_multiple_valid_evidence_references_return_verified() -> None:
    evaluated = evaluate_claim_support_status(
        RootCauseClaim("Cause", ["SQL-1", "SQL-2"]),
        [evidence("SQL-1"), evidence("SQL-2")],
    )

    assert evaluated.status is RootCauseSupportStatus.VERIFIED


def test_valid_and_missing_evidence_references_return_partially_supported() -> None:
    evaluated = evaluate_claim_support_status(
        RootCauseClaim("Cause", ["SQL-1", "SQL-2"]),
        [evidence("SQL-1")],
    )

    assert evaluated.status is RootCauseSupportStatus.PARTIALLY_SUPPORTED


def test_multiple_evidence_references_with_none_found_return_unsupported() -> None:
    evaluated = evaluate_claim_support_status(
        RootCauseClaim("Cause", ["SQL-1", "SQL-2"]),
        [evidence("SQL-3")],
    )

    assert evaluated.status is RootCauseSupportStatus.UNSUPPORTED


def test_duplicate_valid_evidence_references_return_verified() -> None:
    evaluated = evaluate_claim_support_status(
        RootCauseClaim("Cause", ["SQL-1", "SQL-1"]),
        [evidence("SQL-1")],
    )

    assert evaluated.status is RootCauseSupportStatus.VERIFIED


def test_duplicate_missing_evidence_references_return_unsupported() -> None:
    evaluated = evaluate_claim_support_status(
        RootCauseClaim("Cause", ["SQL-1", "SQL-1"]),
        [evidence("SQL-2")],
    )

    assert evaluated.status is RootCauseSupportStatus.UNSUPPORTED


def test_original_claim_conclusion_and_evidence_refs_remain_unchanged() -> None:
    original = RootCauseClaim("Original cause", ["SQL-1", "SQL-2"])

    evaluated = evaluate_claim_support_status(original, [evidence("SQL-1")])

    assert original.conclusion == "Original cause"
    assert original.evidence_refs == ["SQL-1", "SQL-2"]
    assert original.status is RootCauseSupportStatus.NOT_EVALUATED
    assert evaluated.conclusion == original.conclusion
    assert evaluated.evidence_refs == original.evidence_refs
    assert evaluated is not original


def test_contradicted_is_not_assigned_automatically() -> None:
    cases = [
        RootCauseClaim("Empty"),
        RootCauseClaim("Valid", ["SQL-1"]),
        RootCauseClaim("Missing", ["SQL-2"]),
    ]

    statuses = {evaluate_claim_support_status(claim, [evidence("SQL-1")]).status for claim in cases}

    assert RootCauseSupportStatus.CONTRADICTED not in statuses


def test_serialization_preserves_derived_support_status() -> None:
    evaluated = evaluate_claim_support_status(RootCauseClaim("Cause", ["SQL-1"]), [evidence("SQL-1")])

    payload = json.loads(json.dumps(asdict(evaluated)))

    assert payload["status"] == "VERIFIED"
