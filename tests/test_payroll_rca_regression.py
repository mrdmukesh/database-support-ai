from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path

import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent, detect_intent
from regression.payroll_contract import Scenario, create_case, validate_result

DATA = Path(__file__).parent / "regression" / "data" / "payroll_rca_scenarios.json"


def _load_scenarios() -> list[Scenario]:
    records = json.loads(DATA.read_text(encoding="utf-8"))
    required = {item.name for item in fields(Scenario)}
    assert len(records) == 100
    assert all(required - {"expected_root_cause_concepts", "required_evidence_types", "forbidden_claims"} <= set(record) for record in records)
    assert len({record["case_id"] for record in records}) == len(records)
    return [Scenario(**record) for record in records]


SCENARIOS = _load_scenarios()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda case: f"agents-{case.case_id}")
def test_backend_agents_extract_key_and_investigation_intent(scenario: Scenario) -> None:
    entities = extract_entities(scenario.test_question)
    extracted = {(item.entity_type, item.value) for item in entities.entities}
    assert ("business_identifier", scenario.test_employee_or_key) in extracted
    assert detect_intent(scenario.test_question).intent not in {
        InvestigationIntent.UNKNOWN,
        InvestigationIntent.GENERAL_DATABASE_QUESTION,
    }


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda case: case.case_id)
def test_payroll_rca_reasoning_contract(scenario: Scenario) -> None:
    _, result = create_case(scenario, key=f"RENAMED-{scenario.case_id}")
    assert validate_result(scenario, result) == []


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda case: f"rename-{case.case_id}")
def test_contract_is_invariant_to_business_key_and_question_wording(scenario: Scenario) -> None:
    rewritten = replace(scenario, test_question=f"Please diagnose: {scenario.observed_symptom} ({scenario.seeded_defect}).")
    _, first = create_case(rewritten, key="ALPHA-KEY")
    _, second = create_case(rewritten, key="OMEGA-KEY")
    assert first == second
    assert validate_result(rewritten, second) == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda r: replace(r, business_objects=("incident_knowledge_base.root_cause",)), "knowledge table"),
        (lambda r: replace(r, business_objects=("shipping.orders",)), "business object is unrelated"),
        (lambda r: replace(r, procedures=("send_marketing_email",)), "procedure is unrelated"),
        (lambda r: replace(r, root_cause="A network outage caused everything"), "root cause is unsupported"),
        (lambda r: replace(r, evidence_rows=0, citations=(), status="AI_ANSWERED"), "AI_ANSWERED"),
        (lambda r: replace(r, evidence_rows=0, confidence=.95, status="INSUFFICIENT_DATABASE_EVIDENCE"), "confidence is inflated"),
    ],
)
def test_quality_guard_rejects_regressions(mutation, message: str) -> None:
    scenario = SCENARIOS[0]
    _, valid = create_case(scenario)
    assert any(message in failure for failure in validate_result(scenario, mutation(valid)))
