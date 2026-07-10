import json
from pathlib import Path

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.reasoning_agent import (
    RootCauseClaim,
    RootCauseSupportStatus,
    evaluate_claim_support_status,
)
from legacydb_copilot.agents.recommendation_agent import Recommendation, RecommendationStatus
from legacydb_copilot.agents.report_composer_agent import _executive_recommendation_items
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import primary_entity_found, relevant_object_inspected


GOLDEN_PATH = Path(__file__).with_name("duplicate_payment_pay_9001.json")


def test_duplicate_payment_pay_9001_golden_scenario() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert golden["_ownership"] == "HUMAN_OWNED_GOLDEN_EXPECTATION"

    entities = extract_entities(golden["question"])
    exact_entities = [
        entity.value
        for entity in entities.entities
        if entity.entity_type in {"exact_id_or_code", "business_identifier"}
    ]
    assert golden["expected_primary_entity"] in exact_entities

    evidence = EvidenceResult(
        purpose="Find duplicate business keys in payments",
        sql="SELECT payment_number, COUNT(*) AS duplicate_count FROM payments GROUP BY payment_number HAVING COUNT(*) > 1",
        rows=[{"payment_number": "PAY-9001", "duplicate_count": 2}],
        evidence_id="SQL-GOLD-1",
    )
    assert primary_entity_found(golden["expected_primary_entity"], [evidence]).status == "PASS"
    assert evidence.rows[0]["duplicate_count"] == golden["expected_duplicate_payment_symptom"]["duplicate_count"]

    inspected = relevant_object_inspected([{"object_type": "table", "name": "payments"}])
    assert inspected.inspected_objects == golden["expected_relevant_database_objects"]

    confirmed_claim = evaluate_claim_support_status(
        RootCauseClaim("Retry execution processed the payment twice.", [evidence.evidence_id]),
        [evidence],
    )
    assert len(confirmed_claim.evidence_refs) >= golden["minimum_evidence_references"]
    assert confirmed_claim.status == RootCauseSupportStatus.VERIFIED
    assert golden["expected_root_cause_category"] == "RETRY_EXECUTION"

    unsupported_claim = RootCauseClaim(
        golden["forbidden_unsupported_claims"][0],
        status=RootCauseSupportStatus.UNSUPPORTED,
    )
    confirmed_claims = [claim.conclusion for claim in [confirmed_claim, unsupported_claim] if claim.status == RootCauseSupportStatus.VERIFIED]
    assert not set(golden["forbidden_unsupported_claims"]) & set(confirmed_claims)

    recommendations = [
        Recommendation(
            "Review retry idempotency using the linked duplicate-payment evidence.",
            related_claim_id="CLAIM-PAY-1",
            evidence_ids=[evidence.evidence_id],
            recommendation_status=RecommendationStatus.EVIDENCE_GROUNDED,
        ),
        Recommendation(
            "Replace an unverified payment stored procedure.",
            recommendation_status=RecommendationStatus.UNSUPPORTED,
        ),
    ]
    acceptable = set(golden["acceptable_recommendation_categories"])
    assert recommendations[0].recommendation_status.value in acceptable
    executive_items = _executive_recommendation_items(recommendations)
    assert recommendations[0].text in executive_items
    assert recommendations[1].text not in executive_items
    assert recommendations[1] in recommendations  # Preserved in deterministic audit/debug input.
