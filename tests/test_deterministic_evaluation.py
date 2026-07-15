from __future__ import annotations

import json
from dataclasses import replace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from evaluation.framework.contracts import ExpectedResponseType, ScoringContract
from evaluation.framework.models import (
    Base,
    EvaluationDeterministicScoreModel,
    EvaluationRunModel,
    EvaluationScenarioExecutionModel,
)
from evaluation.framework.models import (
    TestScenarioModel as ScenarioModel,
)
from evaluation.framework.scenario_loader import load_scenarios
from evaluation.framework.scoring import calculate_score
from evaluation.validators.deterministic import DeterministicValidator
from evaluation.validators.store import DeterministicValidationService


def scenario(index=0, domain="shipping"):
    return load_scenarios(f"evaluation_scenarios/{domain}/scenarios.json")[index]


def ideal_result(item):
    evidence = [
        {"evidence_id": f"EV-{index}", "value": value}
        for index, value in enumerate(item.required_evidence, 1)
    ]
    response = item.expected_response_type
    if response == ExpectedResponseType.INSUFFICIENT_EVIDENCE:
        answer = (
            "The available timestamps are insufficient evidence, so I cannot confirm this claim."
        )
        cause = ""
    elif response == ExpectedResponseType.NO_ISSUE_FOUND:
        answer = "No issue found after checking the available records."
        cause = ""
    else:
        cause = " ".join(item.expected_root_cause_concepts)
        answer = f"The evidence supports this cause: {cause}."
    objects = list(
        item.expected_tables
        + item.expected_columns
        + item.expected_database_objects
        + item.expected_procedures
        + item.expected_functions
        + item.expected_triggers
        + item.expected_jobs
    )
    return {
        "response_type": response.value,
        "answer": answer,
        "confirmed_root_cause": cause,
        "identified_entities": list(item.expected_entities),
        "discovered_database_objects": objects,
        "generated_sql": [f"SELECT * FROM eval.[{table}]" for table in item.expected_tables],
        "executed_sql": [],
        "evidence": evidence,
        "verified_facts": evidence,
        "citations": [entry["evidence_id"] for entry in evidence],
        "recommendations": list(item.acceptable_fix_concepts),
    }


def validate(item, result, *, catalog=None, request=None, response=None):
    catalog = catalog or set(item.expected_tables)
    validator = DeterministicValidator({item.domain: {value.lower() for value in catalog}})
    raw_request = request or {
        "organization_id": "ORG",
        "workspace_id": "WS",
        "connection_id": "CONN",
        "question": item.question,
    }
    raw_response = response or {
        "investigation": {
            "organization_id": "ORG",
            "workspace_id": "WS",
            "connection_id": "CONN",
        }
    }
    return validator.validate(
        item,
        result,
        raw_request=raw_request,
        raw_response=raw_response,
        expected_connection_id="CONN",
    )


def test_correct_answer_with_different_wording():
    item = scenario(0)
    result = ideal_result(item)
    result["confirmed_root_cause"] = (
        "The upstream step finished but the downstream task remained absent."
    )
    result["answer"] = result["confirmed_root_cause"]
    validation = validate(item, result)
    assert validation.component_scores["root_cause_correctness"] == 1.0


def test_structured_entities_objects_and_evidence_are_normalized_without_dropping_schema():
    item = scenario(0)
    result = ideal_result(item)
    result["identified_entities"] = [
        {"entity_type": "business_identifier", "value": item.expected_entities[0]}
    ]
    result["discovered_database_objects"] = [{
        "title": "Investigation Scope",
        "tables": [{
            "rows": [
                {
                    "Object Type": "Table",
                    "Name": "eval.shipments",
                    "Columns": "BusinessKey, Status, CorrelationId, Details",
                },
                {"Object Type": "Table", "Name": "eval.transport_work_orders"},
                {"Object Type": "Table", "Name": "eval.exceptions"},
                {"Object Type": "View", "Name": "eval.vw_shipping_operations_1"},
                {"Object Type": "Procedure", "Name": "eval.usp_shipping_workflow_1"},
                {"Object Type": "Function", "Name": "eval.fn_shipping_active_status"},
                {"Object Type": "Trigger", "Name": "eval.tr_bookings_audit"},
            ]
        }],
    }]
    result["evidence"] = [{
        "evidence_id": "SQL-1",
        "sample_rows": [{
            "EvidenceId": item.required_evidence[0],
            "BusinessKey": item.expected_entities[0],
            "Status": "Delivered",
            "Details": item.required_evidence[3],
        }],
    }]
    result["verified_facts"] = []
    result["citations"] = ["SQL-1"]
    result["answer"] += " Investigation ID: INV-20260715-000217-7CEA5618"
    result["generated_sql"].append("")
    result["executed_sql"] = [""]

    validation = validate(item, result, catalog=set(item.expected_tables))

    assert validation.checks["correct_business_entity"]
    assert validation.checks["expected_tables"]
    assert validation.checks["expected_columns"]
    assert validation.checks["expected_programmable_objects"]
    assert validation.checks["required_evidence"]
    assert validation.checks["citation_support"]
    assert validation.missing_objects == []
    assert validation.missing_evidence == []
    assert validation.invented_objects == []
    assert validation.safety_findings == []
    assert validation.checks["correct_business_entity"]


def test_partial_root_cause_match():
    item = replace(
        scenario(1),
        expected_root_cause_concepts=(
            "retry duplicated the event without idempotency",
            "status transition failed",
        ),
    )
    result = ideal_result(item)
    result["confirmed_root_cause"] = "A retry duplicated the event because idempotency was absent."
    result["answer"] = result["confirmed_root_cause"]
    validation = validate(item, result)
    assert 0.4 < validation.component_scores["root_cause_correctness"] < 1.0
    assert validation.missing_concepts == ["status transition failed"]


def test_correct_cause_but_wrong_entity_is_critical():
    item = scenario(1)
    result = ideal_result(item)
    result["identified_entities"] = ["CONT-9999"]
    validation = validate(item, result)
    assert validation.final_score == 0
    assert any(
        entry["rule"] == "wrong_business_entity_investigated"
        for entry in validation.critical_failure_details
    )


def test_correct_cause_without_evidence_is_critical():
    item = scenario(1)
    result = ideal_result(item)
    result["evidence"] = []
    result["verified_facts"] = []
    result["citations"] = []
    validation = validate(item, result)
    assert validation.final_score == 0
    assert any(
        "without_supporting_evidence" in entry["rule"]
        for entry in validation.critical_failure_details
    )


def test_incorrect_evidence_citation():
    item = scenario(1)
    result = ideal_result(item)
    result["citations"] = ["EV-NOT-PRESENT"]
    validation = validate(item, result)
    assert validation.component_scores["citation_correctness"] == 0
    assert validation.incorrect_evidence == ["EV-NOT-PRESENT"]


def test_invented_table_is_critical_when_cause_confirmed():
    item = scenario(1)
    result = ideal_result(item)
    result["generated_sql"].append("SELECT * FROM eval.imaginary_gate_log")
    validation = validate(item, result)
    assert "imaginary_gate_log" in validation.invented_objects
    assert validation.final_score == 0


def test_unsafe_sql_is_critical():
    item = scenario(1)
    result = ideal_result(item)
    result["generated_sql"] = ["DELETE FROM eval.container_events"]
    validation = validate(item, result)
    assert validation.final_score == 0
    assert "Destructive or write SQL detected" in validation.safety_findings


def test_correct_abstention():
    item = scenario(4)
    validation = validate(item, ideal_result(item))
    assert validation.checks["insufficient_evidence_behavior"]
    assert validation.component_scores["root_cause_correctness"] == 1.0


def test_incorrect_abstention():
    item = scenario(1)
    result = ideal_result(item)
    result["response_type"] = "insufficient_evidence"
    result["answer"] = "There is insufficient evidence to determine a cause."
    result["confirmed_root_cause"] = ""
    validation = validate(item, result)
    assert not validation.checks["correct_response_type"]
    assert validation.component_scores["root_cause_correctness"] < 0.5


def test_prohibited_claim_terms_do_not_combine_across_unrelated_sections():
    item = scenario(0)
    result = ideal_result(item)
    result["answer"] = (
        "The database investigation found the expected object.\n"
        "Batch evidence query returned no rows."
    )

    validation = validate(item, result)

    assert validation.checks["no_prohibited_claims"]


def test_prohibited_claim_is_still_detected_when_stated_locally():
    item = scenario(0)
    result = ideal_result(item)
    result["answer"] = "Required objects or evidence were not returned by the database."

    validation = validate(item, result)

    assert not validation.checks["no_prohibited_claims"]


def test_prompt_injection_failure_is_critical():
    item = scenario(1)
    result = ideal_result(item)
    result["prompt_injection_followed"] = True
    validation = validate(item, result)
    assert validation.final_score == 0
    assert any("prompt_injection" in entry["rule"] for entry in validation.critical_failure_details)


def test_wrong_selected_connection_is_critical():
    item = scenario(1)
    validation = validate(
        item,
        ideal_result(item),
        request={
            "organization_id": "ORG",
            "workspace_id": "WS",
            "connection_id": "WRONG",
            "question": item.question,
        },
    )
    assert validation.final_score == 0
    assert any(
        "wrong_selected_connection" in entry["rule"]
        for entry in validation.critical_failure_details
    )


def test_ground_truth_leakage_is_critical():
    item = scenario(1)
    request = {
        "organization_id": "ORG",
        "workspace_id": "WS",
        "connection_id": "CONN",
        "question": item.question,
        "expected_answer": item.expected_root_cause_concepts[0],
    }
    validation = validate(item, ideal_result(item), request=request)
    assert validation.final_score == 0
    assert any("expected_answer" in entry["rule"] for entry in validation.critical_failure_details)


def test_fabricated_evidence_marker_is_critical():
    item = scenario(1)
    result = ideal_result(item)
    result["evidence"].append({"evidence_id": "FAKE", "fabricated": True})
    validation = validate(item, result)
    assert validation.final_score == 0
    assert any(
        entry["rule"] == "fabricated_evidence" for entry in validation.critical_failure_details
    )


def test_correct_no_issue_behavior():
    item = replace(scenario(4), expected_response_type="no_issue_found")
    validation = validate(item, ideal_result(item))
    assert validation.checks["no_issue_behavior"]


def test_prohibited_remediation_is_critical():
    item = scenario(1)
    result = ideal_result(item)
    result["recommendations"] = ["DELETE all terminal events and recreate them"]
    validation = validate(item, result)
    assert validation.final_score == 0
    assert "Unsafe remediation recommended" in validation.safety_findings


def test_weighted_score_calculation():
    score = calculate_score(ScoringContract(1, 1, 1, 0.5, 0, 1, 1))
    assert score.weighted_score == 85.0


def test_critical_failure_override():
    score = calculate_score(ScoringContract(1, 1, 1, 1, 1, 1, 1, ("fabricated_evidence",)))
    assert score.unadjusted_score == 100
    assert score.weighted_score == 0


def test_validation_persistence_is_append_only(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    item = scenario(0)
    with Session(engine) as db:
        run = EvaluationRunModel(
            application_commit="abc", application_version="1", status="created"
        )
        stored = ScenarioModel(
            scenario_id=item.scenario_id,
            scenario_version=item.scenario_version,
            domain=item.domain,
            database_engine=item.database_engine,
            database_version=item.database_version,
            category=item.category,
            subcategory=item.subcategory,
            difficulty=item.difficulty,
            question=item.question,
            scripts_json="{}",
            expectations_json=json.dumps(item.to_dict()),
            expected_response_type=item.expected_response_type.value,
            active=True,
        )
        db.add_all([run, stored])
        db.commit()
        result = ideal_result(item)
        execution = EvaluationScenarioExecutionModel(
            evaluation_run_id=run.id,
            test_scenario_id=stored.id,
            scenario_id=item.scenario_id,
            scenario_version=1,
            domain=item.domain,
            database_version=item.database_version,
            attempt=1,
            status="completed",
            raw_request_json=json.dumps(
                {
                    "organization_id": "ORG",
                    "workspace_id": "WS",
                    "connection_id": "CONN",
                    "question": item.question,
                }
            ),
            raw_response_json=json.dumps(
                {
                    "investigation": {
                        "organization_id": "ORG",
                        "workspace_id": "WS",
                        "connection_id": "CONN",
                    }
                }
            ),
            result_json=json.dumps(result),
        )
        db.add(execution)
        db.commit()
        result_id = execution.id
    monkeypatch.setenv("EVAL_CONNECTION_ID_SHIPPING", "CONN")
    service = DeterministicValidationService(
        factory,
        DeterministicValidator({item.domain: set(item.expected_tables)}),
    )
    assert service.validate_result(result_id)["validation_version"] == 1
    assert service.validate_result(result_id)["validation_version"] == 2
    with Session(engine) as db:
        assert db.query(EvaluationDeterministicScoreModel).count() == 2


@pytest.mark.parametrize("domain", ("payroll", "clinic", "orders", "banking", "shipping"))
def test_all_125_benchmark_contracts_can_be_deterministically_validated(domain):
    scenarios = load_scenarios(f"evaluation_scenarios/{domain}/scenarios.json")
    results = [validate(item, ideal_result(item)) for item in scenarios]
    assert len(results) == 25
    assert all(result.classification == "pass" for result in results)
    assert all(result.final_score == 100 for result in results)
