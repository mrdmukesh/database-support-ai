from dataclasses import asdict
import json

from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    RootCauseClaim,
    RootCauseSupportStatus,
    build_deterministic_root_cause_claim,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.llm_reasoning_service import convert_llm_claim_to_root_cause_claim


def reasoning(root_causes) -> ReasoningResult:
    return ReasoningResult("Summary", root_causes, [], [], [], [], [], [], [])


def test_structured_root_cause_claims_are_accepted() -> None:
    claim = RootCauseClaim("Cause", ["SQL-1"], RootCauseSupportStatus.VERIFIED)

    result = reasoning([claim])

    assert result.likely_root_causes == [claim]


def test_legacy_root_cause_strings_are_converted_safely() -> None:
    result = reasoning(["Legacy cause"])

    assert result.likely_root_causes == [RootCauseClaim("Legacy cause")]
    assert result.likely_root_causes[0].status is RootCauseSupportStatus.NOT_EVALUATED


def test_structured_reasoning_result_serialization_works() -> None:
    result = reasoning([RootCauseClaim("Cause", ["SQL-1"], RootCauseSupportStatus.VERIFIED)])

    payload = json.loads(json.dumps(asdict(result)))

    assert payload["likely_root_causes"][0] == {
        "conclusion": "Cause",
        "evidence_refs": ["SQL-1"],
        "status": "VERIFIED",
    }


def test_llm_structured_claim_keeps_evidence_references() -> None:
    evidence = EvidenceResult("Inspect", "SELECT 1", [], evidence_id="SQL-1")
    claim = convert_llm_claim_to_root_cause_claim(
        {"conclusion": "LLM cause", "evidence_refs": ["SQL-1"]}, [evidence]
    )

    result = reasoning([claim])

    assert result.likely_root_causes[0].evidence_refs == ["SQL-1"]
    assert result.likely_root_causes[0].status is RootCauseSupportStatus.VERIFIED


def test_deterministic_structured_claim_keeps_evidence_references() -> None:
    evidence = EvidenceResult("Inspect", "SELECT 1", [], evidence_id="SQL-1")
    claim = build_deterministic_root_cause_claim("Deterministic cause", ["SQL-1"], [evidence])

    result = reasoning([claim])

    assert result.likely_root_causes[0].evidence_refs == ["SQL-1"]
    assert result.likely_root_causes[0].status is RootCauseSupportStatus.VERIFIED
