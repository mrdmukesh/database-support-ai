from copy import deepcopy

import pytest

from legacydb_copilot.agents.reasoning_agent import RootCauseClaim, RootCauseSupportStatus
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.llm_reasoning_service import (
    _cited_items,
    convert_llm_claim_to_root_cause_claim,
)


def evidence(evidence_id: str) -> EvidenceResult:
    return EvidenceResult("Inspect", "SELECT 1", [], evidence_id=evidence_id)


def test_valid_raw_llm_claim_converts_to_root_cause_claim() -> None:
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "Retry processing created a duplicate.", "evidence_refs": ["SQL-1"]},
        [evidence("SQL-1")],
    )

    assert isinstance(claim, RootCauseClaim)
    assert claim.conclusion == "Retry processing created a duplicate."


def test_one_valid_llm_claim_reference_produces_verified() -> None:
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "Cause", "evidence_refs": ["SQL-1"]},
        [evidence("SQL-1")],
    )

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.VERIFIED


def test_multiple_valid_llm_claim_references_are_preserved() -> None:
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "Cause", "evidence_refs": ["SQL-1", "SQL-2"]},
        [evidence("SQL-1"), evidence("SQL-2")],
    )

    assert claim is not None
    assert claim.evidence_refs == ["SQL-1", "SQL-2"]
    assert claim.status is RootCauseSupportStatus.VERIFIED


def test_mixed_llm_claim_references_produce_partially_supported() -> None:
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "Cause", "evidence_refs": ["SQL-1", "SQL-2"]},
        [evidence("SQL-1")],
    )

    assert claim is not None
    assert claim.evidence_refs == ["SQL-1", "SQL-2"]
    assert claim.status is RootCauseSupportStatus.PARTIALLY_SUPPORTED


def test_all_missing_llm_claim_references_produce_unsupported() -> None:
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "Cause", "evidence_refs": ["SQL-2"]},
        [evidence("SQL-1")],
    )

    assert claim is not None
    assert claim.status is RootCauseSupportStatus.UNSUPPORTED


@pytest.mark.parametrize("raw_claim", [{"conclusion": "Cause", "evidence_refs": []}, {"conclusion": "Cause"}])
def test_empty_or_missing_llm_claim_references_produce_not_evaluated(raw_claim: dict) -> None:
    claim = convert_llm_claim_to_root_cause_claim(raw_claim, [evidence("SQL-1")])

    assert claim is not None
    assert claim.evidence_refs == []
    assert claim.status is RootCauseSupportStatus.NOT_EVALUATED


@pytest.mark.parametrize("conclusion", ["", "   ", None])
def test_blank_llm_claim_conclusion_is_rejected(conclusion) -> None:
    assert convert_llm_claim_to_root_cause_claim({"conclusion": conclusion}, []) is None


@pytest.mark.parametrize("malformed_refs", [{"id": "SQL-1"}, 42, ["SQL-1", {"id": "SQL-2"}, 7, None]])
def test_malformed_llm_claim_references_do_not_crash(malformed_refs) -> None:
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "Cause", "evidence_refs": malformed_refs},
        [evidence("SQL-1")],
    )

    assert claim is not None


def test_duplicate_llm_claim_references_do_not_change_verified_status() -> None:
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "Cause", "evidence_refs": ["SQL-1", "SQL-1"]},
        [evidence("SQL-1")],
    )

    assert claim is not None
    assert claim.evidence_refs == ["SQL-1", "SQL-1"]
    assert claim.status is RootCauseSupportStatus.VERIFIED


def test_llm_claim_input_dictionary_is_not_mutated() -> None:
    raw_claim = {"conclusion": " Cause ", "evidence_refs": [" SQL-1 ", ""]}
    original = deepcopy(raw_claim)

    convert_llm_claim_to_root_cause_claim(raw_claim, [evidence("SQL-1")])

    assert raw_claim == original


def test_llm_claim_conclusion_is_not_flattened_with_evidence_text() -> None:
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "Cause", "evidence_refs": ["SQL-1"]},
        [evidence("SQL-1")],
    )

    assert claim is not None
    assert claim.conclusion == "Cause"


def test_existing_cited_items_behavior_remains_unchanged() -> None:
    result = _cited_items(
        [{"conclusion": "Cause", "evidence_refs": ["SQL-1"]}],
        "conclusion",
    )

    assert result == ["Cause Evidence: SQL-1."]
