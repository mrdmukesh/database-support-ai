from legacydb_copilot.agents.recommendation_agent import Recommendation, RecommendationStatus
from legacydb_copilot.agents.report_composer_agent import _executive_recommendation_items


def test_evidence_grounded_recommendation_displays_normally() -> None:
    recommendation = Recommendation(
        "Add the confirmed uniqueness constraint.",
        recommendation_status=RecommendationStatus.EVIDENCE_GROUNDED,
    )

    assert _executive_recommendation_items([recommendation]) == [
        "Add the confirmed uniqueness constraint."
    ]


def test_general_best_practice_recommendation_is_clearly_labeled() -> None:
    recommendation = Recommendation(
        "Add recurrence monitoring.",
        recommendation_status=RecommendationStatus.GENERAL_BEST_PRACTICE,
    )

    assert _executive_recommendation_items([recommendation]) == [
        "General best practice: Add recurrence monitoring."
    ]


def test_unsupported_recommendation_is_hidden_but_preserved_for_audit() -> None:
    recommendation = Recommendation(
        "Rewrite the unverified procedure.",
        recommendation_status=RecommendationStatus.UNSUPPORTED,
    )
    audit_recommendations = [recommendation]

    assert _executive_recommendation_items(audit_recommendations) == []
    assert audit_recommendations == [recommendation]
    assert audit_recommendations[0].text == "Rewrite the unverified procedure."
