import json

import pytest

from legacydb_copilot.services.benchmark_runner import GoldenScenarioBenchmarkResult


def test_golden_benchmark_result_serializes_to_json() -> None:
    result = GoldenScenarioBenchmarkResult(
        entity_correct=True,
        relevant_object_found=True,
        evidence_linked=True,
        root_cause_supported=True,
        unsupported_claim_count=1,
        unsupported_recommendation_count=1,
        test_passed=True,
    )

    payload = json.loads(json.dumps(result.to_dict()))

    assert payload == {
        "entity_correct": True,
        "relevant_object_found": True,
        "evidence_linked": True,
        "root_cause_supported": True,
        "unsupported_claim_count": 1,
        "unsupported_recommendation_count": 1,
        "test_passed": True,
    }


def test_golden_benchmark_result_rejects_negative_counts() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        GoldenScenarioBenchmarkResult(
            entity_correct=False,
            relevant_object_found=False,
            evidence_linked=False,
            root_cause_supported=False,
            unsupported_claim_count=-1,
            unsupported_recommendation_count=0,
            test_passed=False,
        )


def test_golden_benchmark_result_serializes_to_concise_markdown() -> None:
    result = GoldenScenarioBenchmarkResult(True, True, True, True, 1, 1, True)

    markdown = result.to_markdown()

    assert "| entity_correct | true |" in markdown
    assert "production-accuracy claim" in markdown
    assert "%" not in markdown
