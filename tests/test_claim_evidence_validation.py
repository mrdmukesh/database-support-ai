from legacydb_copilot.agents.reasoning_agent import RootCauseClaim, validate_claim_evidence_references
from legacydb_copilot.services.evidence_execution_service import EvidenceResult


def evidence(evidence_id: str) -> EvidenceResult:
    return EvidenceResult("Inspect", "SELECT 1", [], evidence_id=evidence_id)


def test_one_valid_evidence_reference() -> None:
    result = validate_claim_evidence_references(RootCauseClaim("Cause", ["SQL-1"]), [evidence("SQL-1")])

    assert result.is_valid is True
    assert result.valid_evidence_refs == ["SQL-1"]
    assert result.missing_evidence_refs == []


def test_multiple_valid_evidence_references() -> None:
    result = validate_claim_evidence_references(
        RootCauseClaim("Cause", ["SQL-1", "SQL-2"]),
        [evidence("SQL-1"), evidence("SQL-2")],
    )

    assert result.is_valid is True
    assert result.valid_evidence_refs == ["SQL-1", "SQL-2"]
    assert result.missing_evidence_refs == []


def test_one_missing_evidence_reference() -> None:
    result = validate_claim_evidence_references(RootCauseClaim("Cause", ["SQL-2"]), [evidence("SQL-1")])

    assert result.is_valid is False
    assert result.valid_evidence_refs == []
    assert result.missing_evidence_refs == ["SQL-2"]


def test_mixture_of_valid_and_missing_evidence_references() -> None:
    result = validate_claim_evidence_references(
        RootCauseClaim("Cause", ["SQL-1", "SQL-3", "SQL-2"]),
        [evidence("SQL-1"), evidence("SQL-2")],
    )

    assert result.is_valid is False
    assert result.valid_evidence_refs == ["SQL-1", "SQL-2"]
    assert result.missing_evidence_refs == ["SQL-3"]


def test_empty_evidence_references_are_valid() -> None:
    result = validate_claim_evidence_references(RootCauseClaim("Cause"), [evidence("SQL-1")])

    assert result.is_valid is True
    assert result.valid_evidence_refs == []
    assert result.missing_evidence_refs == []


def test_duplicate_evidence_references_are_validated_once() -> None:
    result = validate_claim_evidence_references(
        RootCauseClaim("Cause", ["SQL-1", "SQL-1", "SQL-2", "SQL-2"]),
        [evidence("SQL-1"), evidence("SQL-2")],
    )

    assert result.is_valid is True
    assert result.valid_evidence_refs == ["SQL-1", "SQL-2"]
    assert result.missing_evidence_refs == []


def test_unrelated_evidence_ids_do_not_validate_claim_reference() -> None:
    result = validate_claim_evidence_references(
        RootCauseClaim("Cause", ["SQL-3"]),
        [evidence("SQL-1"), evidence("SQL-2"), evidence("PROC-1")],
    )

    assert result.is_valid is False
    assert result.valid_evidence_refs == []
    assert result.missing_evidence_refs == ["SQL-3"]
