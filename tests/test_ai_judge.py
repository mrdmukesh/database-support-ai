from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from evaluation.framework.models import (
    Base,
    EvaluationAIJudgeScoreModel,
    EvaluationDeterministicScoreModel,
    EvaluationHumanReviewFlagModel,
    EvaluationRunModel,
    EvaluationScenarioExecutionModel,
)
from evaluation.framework.models import (
    TestScenarioModel as ScenarioModel,
)
from evaluation.framework.scenario_loader import load_scenarios
from evaluation.judges.ai_judge import (
    AIJudge,
    JudgeConfig,
    JudgeProviderResponse,
    JudgeTransientError,
    build_judge_payload,
    human_review_decision,
    should_run_second_judge,
    validate_judge_json,
)
from evaluation.judges.store import AIJudgeService


def valid_payload(score=80, **overrides):
    payload = {
        "score_scale": "percentage",
        "root_cause_score": score,
        "evidence_score": score,
        "object_discovery_score": score,
        "fix_score": score,
        "citation_score": score,
        "safety_score": score,
        "completeness_score": score,
        "unsupported_claims": [],
        "missing_evidence": [],
        "incorrect_objects": [],
        "incorrect_entities": [],
        "critical_failure": False,
        "human_review_required": False,
        "explanation": "Evidence and conclusions are aligned.",
    }
    payload.update(overrides)
    return payload


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        raw = value if isinstance(value, str) else json.dumps(value)
        return JudgeProviderResponse(
            raw, input_tokens=100, output_tokens=50, estimated_cost_usd=0.01
        )


def invoke(responses, **config_overrides):
    client = FakeClient(responses)
    config = JudgeConfig(retry_backoff_seconds=0, **config_overrides)
    judge = AIJudge(client, config, sleeper=lambda _seconds: None)
    result = judge.invoke(
        model=config.model,
        payload={"scenario_question": "Why?"},
        deterministic_critical=False,
    )
    return result, client, config


def deterministic(score=80, critical=False, response_ok=True):
    return {
        "final_score": score,
        "critical_failure_details": ([{"rule": "fabricated_evidence"}] if critical else []),
        "checks": {"correct_response_type": response_ok},
    }


def test_valid_judge_output():
    result, client, _config = invoke([valid_payload(85)])
    assert result.status == "completed"
    assert result.normalized.weighted_score == 85
    assert result.input_tokens == 100 and result.output_tokens == 50
    assert client.calls[0]["temperature"] == 0


def test_explicit_legacy_point_scores_are_normalized_to_percentages():
    payload = valid_payload()
    payload.update(
        score_scale="legacy_points",
        root_cause_score=30,
        evidence_score=25,
        object_discovery_score=10,
        fix_score=5,
        citation_score=10,
        safety_score=10,
        completeness_score=5,
    )

    result = validate_judge_json(payload)

    assert result.root_cause_score == 100
    assert result.fix_score == 50
    assert result.normalization_occurred is True
    assert result.weighted_score == 95


def test_ambiguous_score_scale_is_rejected():
    payload = valid_payload()
    payload.pop("score_scale")

    try:
        validate_judge_json(payload)
    except Exception as exc:
        assert "score_scale" in str(exc)
    else:
        raise AssertionError("ambiguous judge scores must not be accepted")


def test_contradictory_low_scores_and_positive_narrative_require_review():
    result, _client, config = invoke(
        [valid_payload(5, explanation="Comprehensive, complete, correctly cited and high confidence.")]
    )

    assert "judge_output_inconsistent" in result.normalized.consistency_flags
    decision = human_review_decision(
        result_id="contradiction",
        deterministic_summary=deterministic(90),
        application_confidence=0.9,
        primary=result,
        secondary=None,
        config=config,
    )
    assert "judge_output_inconsistent" in decision.reasons


def test_malformed_json_retries_then_succeeds():
    result, _client, _config = invoke(["not json", valid_payload()])
    assert result.status == "completed"
    assert result.retries == 1
    assert result.raw_responses[0] == "not json"


def test_missing_required_fields_fails_after_bounded_retries():
    result, client, _config = invoke([{"root_cause_score": 10}] * 3)
    assert result.status == "failed"
    assert len(client.calls) == 3
    assert "missing=" in result.error


def test_judge_timeout_is_bounded():
    result, client, _config = invoke([TimeoutError("timed out")] * 3)
    assert result.status == "failed"
    assert len(client.calls) == 3


def test_judge_rate_limit_retries():
    result, _client, _config = invoke(
        [JudgeTransientError("HTTP 429 token=secret"), valid_payload()]
    )
    assert result.status == "completed" and result.retries == 1


def test_judge_cannot_override_deterministic_critical_failure():
    client = FakeClient([valid_payload(100, critical_failure=False)])
    config = JudgeConfig(retry_backoff_seconds=0)
    result = AIJudge(client, config, sleeper=lambda _: None).invoke(
        model=config.model,
        payload={},
        deterministic_critical=True,
    )
    assert result.normalized.critical_failure
    assert result.normalized.human_review_required


def test_large_score_disagreement_flags_review():
    primary, _client, config = invoke([valid_payload(95)])
    decision = human_review_decision(
        result_id="R1",
        deterministic_summary=deterministic(60),
        application_confidence=0.5,
        primary=primary,
        secondary=None,
        config=config,
    )
    assert "ai_deterministic_difference_over_20" in decision.reasons


def test_second_judge_disagreement_flags_review():
    primary, _client, config = invoke([valid_payload(90)], second_model="judge-2")
    secondary, _client2, _config2 = invoke([valid_payload(60)])
    assert should_run_second_judge(primary, 60, config)
    decision = human_review_decision(
        result_id="R2",
        deterministic_summary=deterministic(80),
        application_confidence=0.5,
        primary=primary,
        secondary=secondary,
        config=config,
    )
    assert "two_judges_disagree_over_15" in decision.reasons


def test_confidence_mismatch_review_flag():
    primary, _client, config = invoke([valid_payload(60)])
    decision = human_review_decision(
        result_id="R3",
        deterministic_summary=deterministic(65),
        application_confidence=0.95,
        primary=primary,
        secondary=None,
        config=config,
    )
    assert "high_confidence_low_score" in decision.reasons


def test_random_passed_case_sampling():
    primary, _client, config = invoke([valid_payload(90)], random_pass_sample_rate=1)
    decision = human_review_decision(
        result_id="R4",
        deterministic_summary=deterministic(90),
        application_confidence=0.5,
        primary=primary,
        secondary=None,
        config=config,
    )
    assert decision.random_sampled
    assert "random_passed_case_sample" in decision.reasons


def test_secret_prompt_redaction_and_confidence_exclusion():
    scenario = load_scenarios("evaluation_scenarios/shipping/scenarios.json")[0]
    actual = {
        "answer": "password=hunter2",
        "evidence": [{"authorization": "Bearer abc"}],
        "citations": ["EV-1"],
        "application_confidence": 0.99,
        "report_snapshot": {"application_confidence": 0.99, "confidence_score": 99},
        "hidden_application_prompt": "private prompt",
    }
    payload = build_judge_payload(scenario, actual, deterministic(80))
    rendered = json.dumps(payload)
    assert "hunter2" not in rendered
    assert "Bearer abc" not in rendered
    assert "application_confidence" not in rendered
    assert "hidden_application_prompt" not in rendered
    assert "private prompt" not in rendered


def test_strict_schema_rejects_extra_fields():
    payload = valid_payload()
    payload["chain_of_thought"] = "hidden"
    try:
        validate_judge_json(payload)
    except Exception as exc:
        assert "extra=" in str(exc)
    else:
        raise AssertionError("Strict judge schema accepted an extra field")


def test_all_125_benchmark_scenarios_build_allowlisted_judge_inputs():
    judged = 0
    for domain in ("payroll", "clinic", "orders", "banking", "shipping"):
        for scenario in load_scenarios(f"evaluation_scenarios/{domain}/scenarios.json"):
            actual = {
                "answer": "Synthetic structured answer",
                "identified_entities": list(scenario.expected_entities),
                "evidence": [{"evidence_id": "EV-1"}],
                "citations": ["EV-1"],
                "application_confidence": 0.99,
            }
            payload = build_judge_payload(scenario, actual, deterministic(100))
            result, _client, _config = invoke([valid_payload(100)])
            assert result.status == "completed"
            assert "application_confidence" not in json.dumps(payload)
            judged += 1
    assert judged == 125


def test_judge_versions_prompts_and_human_flags_are_append_only():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    scenario = load_scenarios("evaluation_scenarios/shipping/scenarios.json")[0]
    with Session(engine) as db:
        run = EvaluationRunModel(
            application_commit="abc", application_version="1", status="created"
        )
        stored = ScenarioModel(
            scenario_id=scenario.scenario_id,
            scenario_version=1,
            domain=scenario.domain,
            database_engine=scenario.database_engine,
            database_version=scenario.database_version,
            category=scenario.category,
            subcategory=scenario.subcategory,
            difficulty=scenario.difficulty,
            question=scenario.question,
            scripts_json="{}",
            expectations_json=json.dumps(scenario.to_dict()),
            expected_response_type=scenario.expected_response_type.value,
            active=True,
        )
        db.add_all([run, stored])
        db.commit()
        execution = EvaluationScenarioExecutionModel(
            evaluation_run_id=run.id,
            test_scenario_id=stored.id,
            scenario_id=scenario.scenario_id,
            scenario_version=1,
            domain=scenario.domain,
            database_version=scenario.database_version,
            attempt=1,
            status="completed",
            result_json=json.dumps(
                {
                    "answer": "Synthetic answer",
                    "evidence": [{"evidence_id": "EV-1"}],
                    "citations": ["EV-1"],
                    "application_confidence": 0.9,
                }
            ),
        )
        db.add(execution)
        db.commit()
        score = EvaluationDeterministicScoreModel(
            scenario_execution_id=execution.id,
            validation_version=1,
            root_cause_correctness=0.8,
            evidence_correctness=0.8,
            object_discovery=0.8,
            fix_correctness=0.8,
            citation_correctness=0.8,
            safety=1,
            completeness=0.8,
            unadjusted_score=82,
            final_score=82,
            classification="pass",
            critical_failure=False,
            details_json=json.dumps(deterministic(82)),
        )
        db.add(score)
        db.commit()
        result_id = execution.id
    client = FakeClient([valid_payload(84), valid_payload(85)])
    config = JudgeConfig(retry_backoff_seconds=0)
    service = AIJudgeService(factory, AIJudge(client, config, sleeper=lambda _: None), config)
    assert service.judge_result(result_id)["judge_version"] == 1
    assert service.judge_result(result_id)["judge_version"] == 2
    with Session(engine) as db:
        assert db.query(EvaluationAIJudgeScoreModel).count() == 2
        assert db.query(EvaluationHumanReviewFlagModel).count() == 2
        prompts = [json.loads(row.prompt_json) for row in db.query(EvaluationAIJudgeScoreModel)]
        assert all(prompt["prompt_version"] == "ai-judge-v1" for prompt in prompts)
        assert all("application_confidence" not in json.dumps(prompt) for prompt in prompts)
