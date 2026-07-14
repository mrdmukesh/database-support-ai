from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from evaluation.framework.contracts import ScenarioContract
from evaluation.framework.models import (
    EvaluationAIJudgeScoreModel,
    EvaluationDeterministicScoreModel,
    EvaluationHumanReviewFlagModel,
    EvaluationScenarioExecutionModel,
    TestScenarioModel,
)
from evaluation.framework.redaction import redact
from evaluation.judges.ai_judge import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    AIJudge,
    HumanReviewDecision,
    JudgeConfig,
    JudgeInvocation,
    build_judge_payload,
    human_review_decision,
    should_run_second_judge,
)


class AIJudgeService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        judge: AIJudge | None,
        config: JudgeConfig | None,
    ):
        self.session_factory = session_factory
        self.judge = judge
        self.config = config

    def judge_result(self, result_id: str) -> dict[str, Any]:
        if self.judge is None or self.config is None:
            raise RuntimeError("AI judge client is not configured")
        context = self._load_context(result_id)
        deterministic = context["deterministic"]
        deterministic_summary = json.loads(deterministic.details_json)
        execution = context["execution"]
        scenario = context["scenario"]
        actual = json.loads(execution.result_json)
        payload = build_judge_payload(scenario, actual, deterministic_summary)
        deterministic_critical = deterministic.critical_failure
        primary = self.judge.invoke(
            model=self.config.model,
            payload=payload,
            deterministic_critical=deterministic_critical,
        )
        secondary = None
        if should_run_second_judge(primary, float(deterministic.final_score), self.config):
            secondary = self.judge.invoke(
                model=str(self.config.second_model),
                payload=payload,
                deterministic_critical=deterministic_critical,
            )
        confidence = actual.get("application_confidence")
        decision = human_review_decision(
            result_id=result_id,
            deterministic_summary=deterministic_summary,
            application_confidence=confidence,
            primary=primary,
            secondary=secondary,
            config=self.config,
        )
        version = self._persist(
            deterministic=deterministic,
            execution=execution,
            primary=primary,
            secondary=secondary,
            decision=decision,
        )
        return {
            "result_id": result_id,
            "scenario_id": execution.scenario_id,
            "judge_version": version,
            "deterministic_score": float(deterministic.final_score),
            "deterministic_critical_failure": deterministic_critical,
            "primary": _invocation_output(primary, float(deterministic.final_score)),
            "secondary": (
                _invocation_output(secondary, float(deterministic.final_score))
                if secondary
                else None
            ),
            "human_review": asdict(decision),
        }

    def judge_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.session_factory() as db:
            rows = (
                db.query(EvaluationScenarioExecutionModel.id)
                .join(
                    EvaluationDeterministicScoreModel,
                    EvaluationDeterministicScoreModel.scenario_execution_id
                    == EvaluationScenarioExecutionModel.id,
                )
                .filter(EvaluationScenarioExecutionModel.evaluation_run_id == run_id)
                .order_by(EvaluationScenarioExecutionModel.scenario_id)
                .all()
            )
            result_ids = list(dict.fromkeys(row[0] for row in rows))
        return [self.judge_result(result_id) for result_id in result_ids]

    def list_human_review(self, run_id: str) -> list[dict[str, Any]]:
        with self.session_factory() as db:
            rows = (
                db.query(EvaluationHumanReviewFlagModel, EvaluationScenarioExecutionModel)
                .join(
                    EvaluationDeterministicScoreModel,
                    EvaluationDeterministicScoreModel.id
                    == EvaluationHumanReviewFlagModel.deterministic_score_id,
                )
                .join(
                    EvaluationScenarioExecutionModel,
                    EvaluationScenarioExecutionModel.id
                    == EvaluationDeterministicScoreModel.scenario_execution_id,
                )
                .filter(
                    EvaluationScenarioExecutionModel.evaluation_run_id == run_id,
                    EvaluationHumanReviewFlagModel.required.is_(True),
                )
                .order_by(EvaluationScenarioExecutionModel.scenario_id)
                .all()
            )
            return [
                {
                    "result_id": execution.id,
                    "scenario_id": execution.scenario_id,
                    "judge_version": flag.judge_version,
                    "reasons": json.loads(flag.reasons_json),
                    "random_sampled": flag.random_sampled,
                    "deterministic_critical_failure": flag.deterministic_critical_failure,
                }
                for flag, execution in rows
            ]

    def _load_context(self, result_id: str) -> dict[str, Any]:
        with self.session_factory() as db:
            execution = db.get(EvaluationScenarioExecutionModel, result_id)
            if execution is None:
                raise ValueError(f"Evaluation result not found: {result_id}")
            deterministic = (
                db.query(EvaluationDeterministicScoreModel)
                .filter(EvaluationDeterministicScoreModel.scenario_execution_id == result_id)
                .order_by(EvaluationDeterministicScoreModel.validation_version.desc())
                .first()
            )
            if deterministic is None:
                raise ValueError("Run deterministic validation before AI judging")
            scenario_model = db.get(TestScenarioModel, execution.test_scenario_id)
            if scenario_model is None:
                raise ValueError("Stored scenario contract is missing")
            scenario = ScenarioContract(**json.loads(scenario_model.expectations_json))
            db.expunge(execution)
            db.expunge(deterministic)
            return {
                "execution": execution,
                "deterministic": deterministic,
                "scenario": scenario,
            }

    def _persist(
        self,
        *,
        deterministic: EvaluationDeterministicScoreModel,
        execution: EvaluationScenarioExecutionModel,
        primary: JudgeInvocation,
        secondary: JudgeInvocation | None,
        decision: HumanReviewDecision,
    ) -> int:
        with self.session_factory() as db:
            version = (
                int(
                    db.query(func.max(EvaluationAIJudgeScoreModel.judge_version))
                    .filter(EvaluationAIJudgeScoreModel.deterministic_score_id == deterministic.id)
                    .scalar()
                    or 0
                )
                + 1
            )
            self._add_invocation(db, deterministic, execution, version, 1, primary)
            if secondary:
                self._add_invocation(db, deterministic, execution, version, 2, secondary)
            db.add(
                EvaluationHumanReviewFlagModel(
                    deterministic_score_id=deterministic.id,
                    judge_version=version,
                    required=decision.required,
                    reasons_json=json.dumps(decision.reasons),
                    random_sampled=decision.random_sampled,
                    deterministic_critical_failure=deterministic.critical_failure,
                )
            )
            db.commit()
            return version

    def _add_invocation(
        self,
        db: Session,
        deterministic: EvaluationDeterministicScoreModel,
        execution: EvaluationScenarioExecutionModel,
        version: int,
        index: int,
        invocation: JudgeInvocation,
    ) -> None:
        if self.config is None:
            raise RuntimeError("AI judge configuration is missing")
        score = invocation.normalized.weighted_score if invocation.normalized else 0.0
        db.add(
            EvaluationAIJudgeScoreModel(
                deterministic_score_id=deterministic.id,
                scenario_execution_id=execution.id,
                judge_version=version,
                judge_index=index,
                provider=self.config.provider,
                model=invocation.model,
                prompt_version=PROMPT_VERSION,
                temperature=self.config.temperature,
                prompt_json=json.dumps(
                    redact(
                        {
                            "system_prompt": SYSTEM_PROMPT,
                            "prompt_version": PROMPT_VERSION,
                            "payload": invocation.prompt,
                        }
                    ),
                    default=str,
                ),
                prompt_hash=invocation.prompt_hash,
                raw_response_json=json.dumps(redact(invocation.raw_responses), default=str),
                normalized_result_json=json.dumps(
                    asdict(invocation.normalized) if invocation.normalized else {}, default=str
                ),
                weighted_score=score,
                deterministic_difference=abs(score - float(deterministic.final_score)),
                input_tokens=invocation.input_tokens,
                output_tokens=invocation.output_tokens,
                duration_ms=invocation.duration_ms,
                estimated_cost_usd=invocation.estimated_cost_usd,
                retry_count=invocation.retries,
                status=invocation.status,
                error=redact(invocation.error),
            )
        )


def _invocation_output(invocation: JudgeInvocation, deterministic_score: float) -> dict[str, Any]:
    return {
        "model": invocation.model,
        "status": invocation.status,
        "normalized": asdict(invocation.normalized) if invocation.normalized else None,
        "weighted_score": invocation.normalized.weighted_score if invocation.normalized else None,
        "deterministic_difference": (
            abs(invocation.normalized.weighted_score - deterministic_score)
            if invocation.normalized
            else None
        ),
        "input_tokens": invocation.input_tokens,
        "output_tokens": invocation.output_tokens,
        "estimated_cost_usd": invocation.estimated_cost_usd,
        "duration_ms": invocation.duration_ms,
        "retries": invocation.retries,
        "error": invocation.error,
    }
