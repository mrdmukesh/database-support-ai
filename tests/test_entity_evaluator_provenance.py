from __future__ import annotations

import pytest

from evaluation.framework.entity_provenance import canonicalize_entities
from evaluation.judges.ai_judge import JudgeError, build_judge_payload
from evaluation.validators.deterministic import DeterministicValidator
from tests.test_deterministic_evaluation import ideal_result, scenario


def mixed(value="SHP-5001", internal="ENTITY-1-EXACT-8"):
    return [
        {"entity_type": "exact_id_or_code", "value": value},
        {
            "entity_type": "entity_resolution_diagnostic",
            "extracted_value": value,
            "matched_value": value,
            "match_type": "exact",
            "confidence": 1.0,
            "evidence_id": internal,
            "resolved_table": "eval.shipments",
            "resolved_column": "BusinessKey",
        },
    ]


def test_internal_resolution_id_is_diagnostic_and_canonical_is_business_value():
    value = canonicalize_entities(mixed(), [{"sample_rows": [{"BusinessKey": "SHP-5001"}]}])
    assert value["canonical_investigated_entity"] == "SHP-5001"
    assert value["diagnostics"][0]["evidence_id"] == "ENTITY-1-EXACT-8"
    assert value["evidence_linked_entities"] == ["SHP-5001"]
    assert not value["evaluator_input_defects"]


@pytest.mark.parametrize("value", ["SHP-5001", "5001", "123e4567-e89b-12d3-a456-426614174000"])
def test_valid_business_identifier_shapes_are_preserved(value):
    assert canonicalize_entities([{"entity_type": "business_identifier", "value": value}])["canonical_investigated_entity"] == value


def test_canonical_prefers_database_resolution_then_normalized_then_original():
    resolved = mixed("ship-5001")
    resolved[1]["matched_value"] = "SHP-5001"
    assert canonicalize_entities(resolved)["canonical_investigated_entity"] == "SHP-5001"
    assert canonicalize_entities([{"entity_type": "business_key", "original_entity_text": " Ship ", "normalized_entity_text": "SHIP"}])["canonical_investigated_entity"] == "SHIP"
    assert canonicalize_entities([{"entity_type": "business_key", "original_entity_text": "RAW"}])["canonical_investigated_entity"] == "RAW"


def test_internal_token_in_business_field_is_evaluator_input_defect_and_preserves_score():
    item = scenario()
    actual = ideal_result(item)
    actual["identified_entities"] = ["ENTITY-1-EXACT-8"]
    invalid = DeterministicValidator().validate(item, actual)
    assert invalid.benchmark_validity == "INVALID_EVALUATOR_INPUT"
    assert invalid.final_score == invalid.unadjusted_score
    assert invalid.unadjusted_score > 0
    assert not any(x["rule"] == "wrong_business_entity_investigated" for x in invalid.critical_failure_details)


def test_real_wrong_business_entity_remains_critical():
    item = scenario()
    actual = ideal_result(item)
    actual["identified_entities"] = [{"entity_type": "business_identifier", "value": "CONT-9999"}]
    validation = DeterministicValidator().validate(item, actual)
    assert any(x["rule"] == "wrong_business_entity_investigated" for x in validation.critical_failure_details)


def test_judge_payload_uses_canonical_entity_and_separates_diagnostics():
    item = scenario()
    actual = ideal_result(item)
    actual["identified_entities"] = mixed(item.expected_entities[0])
    payload = build_judge_payload(item, actual, {"unadjusted_score": 90, "critical_failure_details": []})
    assert payload["canonical_investigated_entity"] == item.expected_entities[0]
    assert payload["entity_resolution_diagnostics"][0]["evidence_id"] == "ENTITY-1-EXACT-8"
    assert "identified_entities" not in payload["actual_structured_investigation_result"]


def test_judge_rejects_internal_token_leak():
    item = scenario()
    actual = ideal_result(item)
    actual["identified_entities"] = ["ENTITY-1-EXACT-8"]
    with pytest.raises(JudgeError, match="INVALID_EVALUATOR_INPUT"):
        build_judge_payload(item, actual, {})


def test_multiple_entities_remain_separate_without_scenario_hardcoding():
    values = canonicalize_entities([
        {"entity_type": "business_identifier", "value": "ORDER-42"},
        {"entity_type": "business_identifier", "value": "CUSTOMER-7"},
    ])
    assert [x["canonical_investigated_entity"] for x in values["canonical_entities"]] == ["ORDER-42", "CUSTOMER-7"]
