from dataclasses import asdict
import json

from legacydb_copilot.agents.recommendation_agent import Recommendation, RecommendationStatus


def test_evidence_grounded_recommendation() -> None:
    recommendation = Recommendation(
        text="Add a uniqueness constraint.",
        related_claim_id="CLAIM-1",
        evidence_ids=["SQL-1", "META-1"],
        recommendation_status=RecommendationStatus.EVIDENCE_GROUNDED,
    )

    assert recommendation.text == "Add a uniqueness constraint."
    assert recommendation.related_claim_id == "CLAIM-1"
    assert recommendation.evidence_ids == ["SQL-1", "META-1"]
    assert recommendation.recommendation_status == RecommendationStatus.EVIDENCE_GROUNDED


def test_general_best_practice_recommendation() -> None:
    recommendation = Recommendation("Add monitoring for recurrence.")

    assert recommendation.recommendation_status == RecommendationStatus.GENERAL_BEST_PRACTICE
    assert recommendation.evidence_ids == []


def test_unsupported_recommendation() -> None:
    recommendation = Recommendation(
        "Rewrite the job.",
        recommendation_status=RecommendationStatus.UNSUPPORTED,
    )

    assert recommendation.recommendation_status == RecommendationStatus.UNSUPPORTED


def test_missing_claim_reference_is_backward_compatible() -> None:
    recommendation = Recommendation("Keep the existing recommendation text.")

    assert recommendation.related_claim_id is None
    assert recommendation.text == "Keep the existing recommendation text."


def test_recommendation_serialization() -> None:
    original = Recommendation(
        "Make the write path idempotent.",
        "CLAIM-2",
        ["SQL-2"],
        RecommendationStatus.EVIDENCE_GROUNDED,
    )

    payload = json.loads(json.dumps(asdict(original)))
    restored = Recommendation(**payload)

    assert restored == original
