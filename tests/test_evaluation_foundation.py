from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from evaluation.framework.contracts import (
    CriticalFailure,
    ExpectedResponseType,
    InvestigationResultSnapshotContract,
    ScenarioContract,
    ScoringContract,
)
from evaluation.framework.models import EvaluationRunModel
from evaluation.framework.models import TestScenarioModel as ScenarioModel
from evaluation.framework.persistence import persist_investigation_result
from evaluation.framework.scenario_loader import load_scenarios, select_latest_active
from evaluation.framework.scoring import calculate_score
from legacydb_copilot.db.base import Base


def scenario(**overrides) -> ScenarioContract:
    values = {
        "scenario_id": "payroll-001",
        "domain": "payroll",
        "database_engine": "mysql",
        "database_version": "8.0",
        "category": "correctness",
        "subcategory": "duplicate_payment",
        "difficulty": "medium",
        "question": "Why was payment P-1 duplicated?",
        "baseline_script": "baseline.sql",
        "setup_script": "setup.sql",
        "verification_script": "verify.sql",
        "cleanup_script": "cleanup.sql",
        "expected_response_type": "confirmed_root_cause",
        "expected_entities": ("P-1",),
        "expected_root_cause_concepts": ("retry",),
        "expected_tables": ("payments",),
        "expected_columns": ("payment_id",),
        "expected_database_objects": ("procedure:post_payment",),
        "required_evidence": ("duplicate rows",),
        "acceptable_fix_concepts": ("idempotency",),
        "prohibited_claims": ("trigger exists",),
        "critical_failure_rules": tuple(CriticalFailure),
        "scenario_version": 1,
        "active": True,
    }
    values.update(overrides)
    return ScenarioContract(**values)


def test_contract_validation_accepts_complete_scenario() -> None:
    contract = scenario()
    assert contract.expected_response_type is ExpectedResponseType.CONFIRMED_ROOT_CAUSE
    assert len(contract.critical_failure_rules) == len(CriticalFailure)


def test_weighted_score_calculation() -> None:
    result = calculate_score(ScoringContract(1, 1, 1, 1, 1, 1, 1))
    assert result.weighted_score == 100.0
    partial = calculate_score(ScoringContract(1, 0, 0, 0, 0, 0, 0))
    assert partial.weighted_score == 30.0


def test_critical_failure_overrides_score() -> None:
    result = calculate_score(
        ScoringContract(1, 1, 1, 1, 1, 1, 1, (CriticalFailure.FABRICATED_EVIDENCE,))
    )
    assert result.unadjusted_score == 100.0
    assert result.weighted_score == 0.0
    assert result.critical_failure_override


@pytest.mark.parametrize("response_type", list(ExpectedResponseType))
def test_expected_response_type_handling(response_type: ExpectedResponseType) -> None:
    assert (
        scenario(expected_response_type=response_type.value).expected_response_type is response_type
    )


def test_scenario_versioning_selects_latest_active() -> None:
    selected = select_latest_active(
        [
            scenario(scenario_version=1),
            scenario(scenario_version=2),
            scenario(scenario_version=3, active=False),
        ]
    )
    assert [item.scenario_version for item in selected] == [2]


def test_result_persistence_round_trip() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        run = EvaluationRunModel(application_commit="abc", application_version="0.1.0")
        stored_scenario = ScenarioModel(
            scenario_id="payroll-001",
            scenario_version=1,
            domain="payroll",
            database_engine="mysql",
            database_version="8",
            category="correctness",
            subcategory="duplicate",
            difficulty="medium",
            question="why?",
            scripts_json="{}",
            expectations_json="{}",
            expected_response_type="confirmed_root_cause",
            active=True,
        )
        db.add_all([run, stored_scenario])
        db.commit()
        snapshot = InvestigationResultSnapshotContract(
            investigation_id="INV-1",
            response_type="confirmed_root_cause",
            answer="Supported answer",
            root_cause_claims=("retry",),
            discovered_objects=("payments",),
            citations=("EV-1",),
            raw_response={"confidence": 0.9},
        )
        record = persist_investigation_result(
            db, evaluation_run_id=run.id, test_scenario_id=stored_scenario.id, snapshot=snapshot
        )
        assert record.investigation_id == "INV-1"
        assert json.loads(record.snapshot_json)["citations"] == ["EV-1"]


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"question": ""}, "question"),
        ({"scenario_version": 0}, "scenario_version"),
        ({"required_evidence": ()}, "required_evidence"),
        ({"expected_response_type": "certainly_true"}, "certainly_true"),
    ],
)
def test_invalid_scenario_rejection(override, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        scenario(**override)


def test_all_domain_manifests_preserve_the_five_pilot_definitions() -> None:
    for domain in ("payroll", "clinic", "orders", "banking", "shipping"):
        scenarios = load_scenarios(f"evaluation_scenarios/{domain}/scenarios.json")
        assert sum("-pilot-" in item.scenario_id for item in scenarios) == 5
        assert all(item.domain == domain for item in scenarios)


def test_complete_benchmark_has_required_distribution() -> None:
    from evaluation.framework.benchmark_validator import validate_benchmark

    scenarios = []
    for domain in ("payroll", "clinic", "orders", "banking", "shipping"):
        scenarios.extend(load_scenarios(f"evaluation_scenarios/{domain}/scenarios.json"))
    assert len(scenarios) == 125
    assert validate_benchmark(scenarios) == []
