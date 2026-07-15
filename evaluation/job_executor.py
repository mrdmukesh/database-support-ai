from __future__ import annotations

import json
import os
from types import SimpleNamespace

from evaluation.cli.__main__ import all_scenarios, build_judge_service, build_runner, build_store
from evaluation.judges.ai_judge import PROMPT_VERSION
from evaluation.preflight import DOMAINS, run_preflight
from evaluation.validators.store import DeterministicValidationService


class InProcessEvaluationExecutor:
    """Adapter from durable jobs to the existing runner services; never invokes a shell."""

    def preflight(self, job) -> dict:
        tenant_matches = (
            os.getenv("EVAL_ORGANIZATION_ID") == job.organization_id
            and os.getenv("EVAL_WORKSPACE_ID") == job.workspace_id
        )
        report = run_preflight()
        result = report.to_dict()
        result["checks"].append({"name": "job tenant configuration", "status": "PASS" if tenant_matches else "FAIL", "detail": "worker tenant matches job" if tenant_matches else "worker tenant does not match job"})
        result["passed"] = bool(result["passed"] and tenant_matches)
        return result

    def execute(self, job, should_cancel, update) -> dict:
        config = json.loads(job.configuration_json or "{}")
        args = SimpleNamespace(
            timeout=float(config.get("timeout_seconds") or 600), concurrency=1,
            poll_interval=float(os.getenv("EVAL_POLL_INTERVAL_SECONDS", "2")),
            api_retries=int(os.getenv("EVAL_API_MAX_RETRIES", "3")),
        )
        runner = build_runner(args)
        scenarios = all_scenarios()
        requested = set(json.loads(job.selected_scenarios_json or "[]"))
        if job.run_type == "pilot_smoke":
            selected = []
            for domain in DOMAINS:
                configured = os.getenv(f"EVAL_SMOKE_SCENARIO_{domain.upper()}")
                matches = [item for item in scenarios if item.domain == domain and (item.scenario_id == configured if configured else True)]
                if not matches:
                    raise RuntimeError(f"No active smoke scenario is configured for domain {domain}")
                selected.append(matches[0])
        else:
            selected = [item for item in scenarios if item.scenario_id in requested]
            if len(selected) != len(requested):
                raise RuntimeError("One or more selected scenarios are not active")
        run_id = runner.create_run(job.run_name)
        store = build_store()
        validator = DeterministicValidationService(store.session_factory)
        judge = build_judge_service(store)
        completed = failed = 0
        actual_cost = 0.0
        for index, scenario in enumerate(selected, 1):
            if should_cancel():
                return {"cancelled": True, "run_id": run_id, "completed": completed, "failed": failed, "actual_cost_usd": actual_cost}
            update(scenario.scenario_id, completed, failed, round((index - 1) * 100 / len(selected), 2))
            result = runner.run_scenario(run_id, scenario)
            status = next(row for row in store.statuses(run_id) if row["scenario_id"] == scenario.scenario_id)
            if result.status in {"completed", "partial_application_response"}:
                deterministic = validator.validate_result(status["result_id"])
                judged = judge.judge_result(status["result_id"])
                actual_cost += float(judged.get("primary", {}).get("estimated_cost_usd") or 0)
                completed += 1
            else:
                failed += 1
            update(scenario.scenario_id, completed, failed, round(index * 100 / len(selected), 2))
        return {"run_id": run_id, "completed": completed, "failed": failed, "actual_cost_usd": actual_cost, "prompt_version": PROMPT_VERSION}
