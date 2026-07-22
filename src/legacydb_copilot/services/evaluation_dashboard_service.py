from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from evaluation.framework.models import (
    EvaluationAIJudgeScoreModel,
    EvaluationDeterministicScoreModel,
    EvaluationHumanReviewFlagModel,
    EvaluationRunModel,
    EvaluationScenarioExecutionModel,
    TestScenarioModel,
)
from legacydb_copilot.db.models import EvaluationJobModel


def _json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class EvaluationDashboardService:
    """Read-only projections over immutable evaluation records."""

    def __init__(self, db: Session, *, organization_id: str | None):
        self.db = db
        self.organization_id = organization_id

    def runs(self) -> list[dict[str, Any]]:
        output = []
        for run in self.db.query(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc()).all():
            executions = self._accessible_executions(run.id)
            if not executions:
                continue
            completed = sum(item.status == "completed" for item in executions)
            metadata = _json(run.configuration_json, {})
            protected_reason = self._protected_reason(run, metadata)
            output.append({
                "id": run.id,
                "name": metadata.get("run_name") or run.id,
                "status": "completed" if completed == len(executions) else run.status,
                "created_at": run.created_at,
                "application_commit": run.application_commit,
                "application_version": run.application_version,
                "scenario_count": len(executions),
                "completed_count": completed,
                "is_protected": bool(protected_reason),
                "protection_reason": protected_reason,
            })
        return output

    def delete_runs(self, run_ids: list[str]) -> dict[str, Any]:
        requested = list(dict.fromkeys(run_ids))
        if not requested:
            return {"deleted": [], "protected": [], "missing": [], "requested_count": 0}

        visible_runs = {run["id"]: run for run in self.runs()}
        protected: list[dict[str, str]] = []
        missing: list[str] = []
        deletable_ids: list[str] = []

        for run_id in requested:
            row = visible_runs.get(run_id)
            if row is None:
                missing.append(run_id)
                continue
            if row.get("is_protected"):
                protected.append({
                    "id": run_id,
                    "name": str(row.get("name") or run_id),
                    "reason": str(row.get("protection_reason") or "Protected run"),
                })
                continue
            deletable_ids.append(run_id)

        deleted: list[dict[str, str]] = []
        if deletable_ids:
            run_rows = self.db.query(EvaluationRunModel).filter(EvaluationRunModel.id.in_(deletable_ids)).all()
            deleted = [{"id": row.id, "name": self._run_name(row)} for row in run_rows]
            try:
                self.db.query(EvaluationJobModel).filter(EvaluationJobModel.evaluation_run_id.in_(deletable_ids)).update({"evaluation_run_id": None}, synchronize_session=False)
                self.db.execute(delete(EvaluationRunModel).where(EvaluationRunModel.id.in_(deletable_ids)))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

        return {
            "requested_count": len(requested),
            "deleted": deleted,
            "protected": protected,
            "missing": missing,
        }

    def summary(self, run_id: str) -> dict[str, Any]:
        rows = self.scenarios(run_id)
        completed = [row for row in rows if row["execution_status"] == "completed"]
        scored = [row for row in rows if row["deterministic_score"] is not None]
        judged = [row for row in rows if row["ai_judge_score"] is not None]
        return {
            "run_id": run_id,
            "scenario_count": len(rows),
            "completed_count": len(completed),
            "passed_count": sum(row["classification"] == "pass" for row in rows),
            "failed_count": sum(row["classification"] == "fail" for row in rows),
            "human_review_count": sum(bool(row["human_review_required"]) for row in rows),
            "critical_failure_count": sum(bool(row["critical_failure"]) for row in rows),
            "deterministic_average": round(sum(row["deterministic_score"] for row in scored) / len(scored), 2) if scored else None,
            "ai_judge_average": round(sum(row["ai_judge_score"] for row in judged) / len(judged), 2) if judged else None,
            "total_duration_seconds": round(sum(row["duration_seconds"] for row in rows), 3),
            "total_tokens": sum(row["total_tokens"] for row in rows),
            "total_cost_usd": round(sum(row["cost_usd"] for row in rows), 6),
            "domains": dict(Counter(row["domain"] for row in rows)),
            "statuses": dict(Counter(row["execution_status"] for row in rows)),
        }

    def scenarios(self, run_id: str) -> list[dict[str, Any]]:
        executions = self._accessible_executions(run_id)
        latest_attempt: dict[str, EvaluationScenarioExecutionModel] = {}
        for execution in executions:
            current = latest_attempt.get(execution.scenario_id)
            if current is None or execution.attempt > current.attempt:
                latest_attempt[execution.scenario_id] = execution
        return [self._scenario_row(item) for item in sorted(latest_attempt.values(), key=lambda row: row.scenario_id)]

    def scenario_detail(self, result_id: str) -> dict[str, Any] | None:
        execution = self.db.get(EvaluationScenarioExecutionModel, result_id)
        if execution is None or not self._accessible(execution):
            return None
        row = self._scenario_row(execution)
        scenario = self.db.get(TestScenarioModel, execution.test_scenario_id)
        result = _json(execution.result_json, {})
        deterministic = self._latest_deterministic(execution.id)
        judge = self._latest_judge(execution.id)
        judge_report = self._judge_report(execution.id, judge)
        row.update({
            "question": scenario.question if scenario else "",
            "category": scenario.category if scenario else "",
            "difficulty": scenario.difficulty if scenario else "",
            "investigation_status": execution.investigation_status,
            "answer": result.get("answer", ""),
            "identified_entities": result.get("identified_entities", []),
            "discovered_database_objects": result.get("discovered_database_objects", []),
            "evidence": result.get("evidence", []),
            "citations": result.get("citations", []),
            "recommendations": result.get("recommendations", []),
            "errors": _json(execution.errors_json, []),
            "timings": _json(execution.timing_json, {}),
            "usage_cost": _json(execution.usage_cost_json, {}),
            "deterministic_details": _json(deterministic.details_json, {}) if deterministic else None,
            "judge_result": _json(judge.normalized_result_json, {}) if judge else None,
            "judge_report": judge_report,
        })
        return row

    def human_reviews(self, run_id: str) -> list[dict[str, Any]]:
        return [row for row in self.scenarios(run_id) if row["human_review_required"]]

    def compare(self, baseline_run_id: str, candidate_run_id: str) -> dict[str, Any]:
        baseline = self.summary(baseline_run_id)
        candidate = self.summary(candidate_run_id)
        keys = ("deterministic_average", "ai_judge_average", "completed_count", "passed_count", "human_review_count", "critical_failure_count", "total_duration_seconds", "total_tokens", "total_cost_usd")
        deltas = {}
        for key in keys:
            left, right = baseline.get(key), candidate.get(key)
            deltas[key] = None if left is None or right is None else round(_number(right) - _number(left), 6)
        return {"baseline": baseline, "candidate": candidate, "deltas": deltas}

    def _accessible_executions(self, run_id: str) -> list[EvaluationScenarioExecutionModel]:
        rows = self.db.query(EvaluationScenarioExecutionModel).filter(EvaluationScenarioExecutionModel.evaluation_run_id == run_id).order_by(EvaluationScenarioExecutionModel.scenario_id, EvaluationScenarioExecutionModel.attempt).all()
        return [row for row in rows if self._accessible(row)]

    def _accessible(self, execution: EvaluationScenarioExecutionModel) -> bool:
        if self.organization_id is None:
            return True
        request = _json(execution.raw_request_json, {})
        return request.get("organization_id") == self.organization_id

    def _latest_deterministic(self, execution_id: str):
        return self.db.query(EvaluationDeterministicScoreModel).filter(EvaluationDeterministicScoreModel.scenario_execution_id == execution_id).order_by(EvaluationDeterministicScoreModel.validation_version.desc()).first()

    def _latest_judge(self, execution_id: str):
        return self.db.query(EvaluationAIJudgeScoreModel).filter(EvaluationAIJudgeScoreModel.scenario_execution_id == execution_id, EvaluationAIJudgeScoreModel.judge_index == 1).order_by(EvaluationAIJudgeScoreModel.judge_version.desc()).first()

    def _judge_report(self, execution_id: str, primary) -> dict[str, Any] | None:
        if primary is None:
            return None
        invocations = self.db.query(EvaluationAIJudgeScoreModel).filter(
            EvaluationAIJudgeScoreModel.scenario_execution_id == execution_id,
            EvaluationAIJudgeScoreModel.judge_version == primary.judge_version,
        ).order_by(EvaluationAIJudgeScoreModel.judge_index).all()
        return {
            "judge_version": primary.judge_version,
            "prompt_version": primary.prompt_version,
            "deterministic_difference": _number(primary.deterministic_difference),
            "invocations": [{
                "judge_index": item.judge_index, "provider": item.provider,
                "model": item.model, "status": item.status,
                "weighted_score": _number(item.weighted_score),
                "result": _json(item.normalized_result_json, {}),
                "input_tokens": item.input_tokens, "output_tokens": item.output_tokens,
                "duration_ms": item.duration_ms,
                "estimated_cost_usd": _number(item.estimated_cost_usd),
                "retry_count": item.retry_count, "error": item.error,
            } for item in invocations],
        }

    def _scenario_row(self, execution: EvaluationScenarioExecutionModel) -> dict[str, Any]:
        deterministic = self._latest_deterministic(execution.id)
        judge = self._latest_judge(execution.id)
        review = None
        if deterministic:
            review = self.db.query(EvaluationHumanReviewFlagModel).filter(EvaluationHumanReviewFlagModel.deterministic_score_id == deterministic.id).order_by(EvaluationHumanReviewFlagModel.judge_version.desc()).first()
        timing = _json(execution.timing_json, {})
        usage = _json(execution.usage_cost_json, {})
        token_usage = usage.get("token_usage") or {}
        total_tokens = int(_number(token_usage.get("total_tokens") if isinstance(token_usage, dict) else token_usage))
        if not total_tokens and isinstance(token_usage, dict):
            total_tokens = int(_number(token_usage.get("input_tokens")) + _number(token_usage.get("output_tokens")))
        judge_tokens = (judge.input_tokens + judge.output_tokens) if judge else 0
        return {
            "result_id": execution.id,
            "scenario_id": execution.scenario_id,
            "scenario_version": execution.scenario_version,
            "domain": execution.domain,
            "attempt": execution.attempt,
            "execution_status": execution.status,
            "investigation_id": execution.investigation_id,
            "deterministic_score": _number(deterministic.final_score) if deterministic else None,
            "classification": deterministic.classification if deterministic else None,
            "critical_failure": deterministic.critical_failure if deterministic else False,
            "ai_judge_score": _number(judge.weighted_score) if judge else None,
            "score_difference": _number(judge.deterministic_difference) if judge else None,
            "human_review_required": review.required if review else False,
            "human_review_reasons": _json(review.reasons_json, []) if review else [],
            "duration_seconds": _number(timing.get("total_seconds")),
            "total_tokens": total_tokens + judge_tokens,
            "cost_usd": _number(usage.get("estimated_cost")) + (_number(judge.estimated_cost_usd) if judge else 0),
        }

    def _run_name(self, run: EvaluationRunModel) -> str:
        return str(_json(run.configuration_json, {}).get("run_name") or run.id)

    def _protected_reason(self, run: EvaluationRunModel, metadata: dict[str, Any]) -> str | None:
        name = self._run_name(run).lower()
        suite = str(metadata.get("suite") or "").lower()
        if bool(metadata.get("protected_final_benchmark")):
            return "Protected final benchmark"
        if bool(metadata.get("imported_from_frozen_evidence")):
            return "Imported frozen benchmark"
        if bool(metadata.get("official")):
            return "Official run"
        if bool(metadata.get("frozen")):
            return "Frozen run"
        if bool(metadata.get("release_benchmark")):
            return "Release benchmark"
        if suite == "full-125":
            return "Release benchmark suite"
        if "frozen" in name:
            return "Frozen run"
        if "official" in name:
            return "Official run"
        if "release benchmark" in name:
            return "Release benchmark"
        if "benchmark-125" in name:
            return "Release benchmark"
        return None
