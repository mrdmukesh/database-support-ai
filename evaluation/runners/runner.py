from __future__ import annotations

import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from importlib.metadata import version
from typing import Any

from evaluation.framework.contracts import ScenarioContract
from evaluation.framework.redaction import redact
from evaluation.runners.contracts import (
    DatabaseLifecycle,
    ExecutionResult,
    ExecutionStore,
    InvestigationClient,
    InvestigationResultReader,
    RunnerConfig,
    SetupFailedError,
    TransientAPIError,
)

TERMINAL_STATUSES = {
    "AI_ANSWERED",
    "DEVELOPER_REVIEW",
    "FIX_APPLIED",
    "PENDING_APPROVAL",
    "APPROVED_KNOWLEDGE",
    "REJECTED",
    "CLOSED",
}
FAILED_STATUSES = {
    "setup_failed",
    "api_submission_failed",
    "timeout",
    "polling_failed",
    "persistence_failed",
    "cleanup_failed",
    "interrupted",
}


class EvaluationRunner:
    _domain_locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(
        self,
        *,
        config: RunnerConfig,
        database: DatabaseLifecycle,
        api: InvestigationClient,
        store: ExecutionStore,
        result_reader: InvestigationResultReader | None = None,
        sleeper=time.sleep,
        clock=time.monotonic,
    ):
        self.config = config
        self.database = database
        self.api = api
        self.store = store
        self.result_reader = result_reader
        self.sleeper = sleeper
        self.clock = clock

    def create_run(self, run_name: str) -> str:
        metadata = self.run_metadata()
        return self.store.create_run(run_name=run_name, metadata=metadata)

    def run_metadata(self) -> dict[str, Any]:
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
        except Exception:
            commit = "unknown"
        try:
            app_version = version("legacydb-support-copilot")
        except Exception:
            app_version = "0.1.0"
        import os

        flag_names = (
            "AI_REASONING_ENABLED",
            "LLM_ENABLED",
            "AI_DEBUG_TRACE_ENABLED",
            "VERIFICATION_AGENT_ENABLED",
            "KNOWLEDGE_RETRIEVER_BACKEND",
            "EMBEDDING_PROVIDER",
            "MAX_INVESTIGATION_ROWS",
            "ALLOW_FULL_TABLE_SCAN",
        )
        return {
            "application_commit": commit,
            "application_version": app_version,
            "feature_flags": {name: os.getenv(name) for name in flag_names},
            "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
            "llm_model": os.getenv("LLM_MODEL", "gpt-4.1-mini"),
            "started_at": time.time(),
        }

    def run_scenario(self, run_id: str, scenario: ScenarioContract) -> ExecutionResult:
        lock = self._lock_for(scenario.domain)
        with lock:
            return self._run_locked(run_id, scenario)

    def run_many(self, run_id: str, scenarios: list[ScenarioContract]) -> list[ExecutionResult]:
        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            futures = [
                executor.submit(self.run_scenario, run_id, scenario) for scenario in scenarios
            ]
            return [future.result() for future in as_completed(futures)]

    def _run_locked(self, run_id: str, scenario: ScenarioContract) -> ExecutionResult:
        started = self.clock()
        result = ExecutionResult(
            scenario_id=scenario.scenario_id,
            domain=scenario.domain,
            attempt=self.store.next_attempt(run_id, scenario.scenario_id),
        )
        setup_started = self.clock()
        persistence_error: Exception | None = None
        try:
            self.database.reset(scenario)
            self.database.inject(scenario)
            verification = self.database.verify(scenario)
            result.extracted_result["setup_verification"] = verification
            if not verification.get("verified"):
                raise SetupFailedError("Defect verification did not match expected precondition")
            result.timings["database_setup_seconds"] = self.clock() - setup_started
            payload = self._request_payload(scenario)
            result.raw_request = payload
            submit_started = self.clock()
            submission = self._retry(lambda: self.api.submit(payload), result)
            result.timings["investigation_submission_seconds"] = self.clock() - submit_started
            result.raw_response["submission"] = submission
            result.investigation_id = str(submission.get("investigation_id") or "")
            if not result.investigation_id:
                result.status = "partial_application_response"
            else:
                detail = self._poll(result.investigation_id, result)
                if self.result_reader:
                    context = self.config.context
                    persisted = self.result_reader.read(
                        result.investigation_id,
                        organization_id=context.organization_id,
                        workspace_id=context.workspace_id,
                    )
                    detail = {**detail, **persisted}
                result.raw_response["investigation"] = detail
                result.investigation_status = str(detail.get("status") or "")
                result.extracted_result = {**result.extracted_result, **self._extract(submission, detail)}
                self._capture_optional_metrics(result)
                result.status = (
                    "completed" if detail.get("ai_answer") else "partial_application_response"
                )
        except SetupFailedError as exc:
            result.status = "setup_failed"
            result.errors.append(str(exc))
        except TimeoutError as exc:
            result.status = "timeout"
            result.errors.append(str(exc))
        except TransientAPIError as exc:
            result.status = "polling_failed" if result.investigation_id else "api_submission_failed"
            result.errors.append(str(exc))
        except KeyboardInterrupt:
            result.status = "interrupted"
            result.errors.append("Execution interrupted")
        except Exception as exc:
            result.status = "polling_failed" if result.investigation_id else "api_submission_failed"
            result.errors.append(str(exc))
        finally:
            cleanup_started = self.clock()
            try:
                self.database.cleanup(scenario)
                result.extracted_result["cleanup_status"] = "passed"
            except Exception as exc:
                result.extracted_result["cleanup_status"] = "failed"
                result.errors.append(f"Cleanup failed: {exc}")
                if result.status == "completed":
                    result.status = "cleanup_failed"
            result.timings["cleanup_seconds"] = self.clock() - cleanup_started
            result.timings["total_seconds"] = self.clock() - started
            result.raw_request = redact(result.raw_request)
            result.raw_response = redact(result.raw_response)
            result.errors = redact(result.errors)
            try:
                self.store.persist(run_id, scenario, result)
            except Exception as exc:
                persistence_error = exc
                result.errors.append(f"Persistence failed: {redact(str(exc))}")
                result.status = "persistence_failed"
                result.recovery_artifact = self._write_recovery(run_id, scenario, result)
        if persistence_error:
            return result
        return result

    def _request_payload(self, scenario: ScenarioContract) -> dict[str, Any]:
        context = self.config.context
        return {
            "organization_id": context.organization_id,
            "workspace_id": context.workspace_id,
            "connection_id": context.connection_ids[scenario.domain],
            "user_id": context.user_id,
            "question": scenario.question,
        }

    def _retry(self, call, result: ExecutionResult) -> dict[str, Any]:
        for attempt in range(self.config.max_api_retries + 1):
            try:
                payload, _status = call()
                return payload
            except TransientAPIError:
                if attempt >= self.config.max_api_retries:
                    raise
                result.retries += 1
                self.sleeper(self.config.retry_backoff_seconds * (2**attempt))
        raise AssertionError("unreachable")

    def _poll(self, investigation_id: str, result: ExecutionResult) -> dict[str, Any]:
        started = self.clock()
        deadline = started + self.config.timeout_seconds
        while self.clock() <= deadline:
            detail = self._retry(lambda: self.api.retrieve(investigation_id), result)
            if str(detail.get("status") or "") in TERMINAL_STATUSES:
                result.timings["polling_seconds"] = self.clock() - started
                return detail
            self.sleeper(self.config.poll_interval_seconds)
        raise TimeoutError(f"Investigation {investigation_id} exceeded polling timeout")

    @staticmethod
    def _extract(submission: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
        combined = {**submission, **detail}
        sections = combined.get("report_snapshot", {}).get("sections", [])

        def matching(*terms: str) -> list[Any]:
            return [
                section
                for section in sections
                if any(term in str(section.get("title", "")).lower() for term in terms)
            ]

        return {
            "identified_entities": combined.get(
                "identified_entities", combined.get("extracted_entities", [])
            ),
            "discovered_database_objects": combined.get(
                "discovered_database_objects", matching("object ranking", "investigation scope")
            ),
            "generated_sql": combined.get("generated_sql", combined.get("sql_queries", [])),
            "executed_sql": combined.get("executed_sql", []),
            "evidence": combined.get("evidence", []),
            "citations": combined.get("citations", combined.get("sources", []))
            or matching("references used"),
            "verified_facts": combined.get("verified_facts", []) or matching("verified fact"),
            "interpretations": combined.get("interpretations", [])
            or matching("why it happened", "interpretation"),
            "confirmed_root_cause": combined.get("confirmed_root_cause", "")
            or matching("root cause"),
            "recommendations": combined.get("recommendations", []) or matching("recommendation"),
            "application_confidence": combined.get("confidence_score", combined.get("confidence")),
            "answer": combined.get("ai_answer", ""),
            "report": combined.get("report"),
            "metadata_discovery_duration": combined.get("metadata_discovery_duration"),
            "sql_execution_duration": combined.get("sql_execution_duration"),
            "llm_duration": combined.get("llm_duration"),
            "report_generation_duration": combined.get("report_generation_duration"),
            "token_usage": combined.get("token_usage"),
            "estimated_cost": combined.get("estimated_cost"),
            "report_snapshot": combined.get("report_snapshot", {}),
        }

    def _write_recovery(
        self, run_id: str, scenario: ScenarioContract, result: ExecutionResult
    ) -> str:
        root = self.config.recovery_root / run_id
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{scenario.scenario_id}-attempt-{result.attempt}.json"
        path.write_text(json.dumps(redact(asdict(result)), indent=2, default=str), encoding="utf-8")
        return str(path)

    @staticmethod
    def _capture_optional_metrics(result: ExecutionResult) -> None:
        values = result.extracted_result
        for key in (
            "metadata_discovery_duration",
            "sql_execution_duration",
            "llm_duration",
            "report_generation_duration",
        ):
            if values.get(key) is not None:
                result.timings[key] = values[key]
        if values.get("token_usage") is not None:
            result.usage_cost["token_usage"] = values["token_usage"]
        if values.get("estimated_cost") is not None:
            result.usage_cost["estimated_cost"] = values["estimated_cost"]

    @classmethod
    def _lock_for(cls, domain: str) -> threading.Lock:
        with cls._locks_guard:
            return cls._domain_locks.setdefault(domain, threading.Lock())
