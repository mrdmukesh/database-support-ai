from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Callable, Protocol

from sqlalchemy.orm import Session

from evaluation.framework.redaction import redact
from legacydb_copilot.db.models import EvaluationJobModel


class JobExecutor(Protocol):
    def preflight(self, job: EvaluationJobModel) -> dict: ...
    def execute(self, job: EvaluationJobModel, should_cancel: Callable[[], bool], update: Callable[[str, int, int, float], None]) -> dict: ...


class EvaluationJobWorker:
    """Database-backed worker; safe to run as a separate Azure Container App process."""

    def __init__(self, session_factory, executor: JobExecutor, *, worker_id: str, stale_after_seconds: int = 900):
        self.session_factory = session_factory
        self.executor = executor
        self.worker_id = worker_id
        self.stale_after_seconds = stale_after_seconds

    def recover_stale_jobs(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=self.stale_after_seconds)
        with self.session_factory() as db:
            jobs = db.query(EvaluationJobModel).filter(
                EvaluationJobModel.status.in_(("preflight", "running")),
                EvaluationJobModel.heartbeat_at < cutoff,
            ).all()
            for job in jobs:
                job.status = "queued"
                job.worker_id = ""
                job.heartbeat_at = None
                job.error_json = json.dumps({"code": "worker_restart_recovery", "message": "Stale worker claim was safely requeued."})
            db.commit()
            return len(jobs)

    def run_once(self) -> bool:
        job_id = self._claim()
        if not job_id:
            return False
        try:
            with self.session_factory() as db:
                job = db.get(EvaluationJobModel, job_id)
                preflight = self.executor.preflight(job)
                job.preflight_json = json.dumps(redact(preflight), default=str)
                job.heartbeat_at = datetime.now(UTC)
                if not preflight.get("passed"):
                    job.status = "failed"; job.completed_at = datetime.now(UTC)
                    job.error_json = json.dumps({"code": "preflight_failed", "message": "Mandatory evaluation preflight checks failed."})
                    db.commit(); return True
                if job.cancel_requested_at:
                    job.status = "cancelled"; job.completed_at = datetime.now(UTC); db.commit(); return True
                job.status = "running"; db.commit(); db.refresh(job); db.expunge(job)
            result = self.executor.execute(job, lambda: self._cancel_requested(job_id), lambda *args: self._progress(job_id, *args))
            with self.session_factory() as db:
                job = db.get(EvaluationJobModel, job_id)
                if result.get("cancelled") or job.cancel_requested_at:
                    job.status = "cancelled"
                else:
                    job.evaluation_run_id = result.get("run_id")
                    job.judge_version = str(result.get("judge_version") or job.judge_version)
                    job.prompt_version = str(result.get("prompt_version") or job.prompt_version)
                    job.actual_cost_usd = float(result.get("actual_cost_usd") or 0)
                    failed = int(result.get("failed") or 0)
                    job.status = "partially_completed" if failed else "completed"
                job.completed_at = datetime.now(UTC); job.heartbeat_at = datetime.now(UTC); db.commit()
        except Exception as exc:
            with self.session_factory() as db:
                job = db.get(EvaluationJobModel, job_id)
                job.status = "failed"; job.completed_at = datetime.now(UTC)
                job.error_json = json.dumps({"code": "worker_failure", "message": str(redact(str(exc)))[:500]})
                db.commit()
        return True

    def _claim(self) -> str | None:
        with self.session_factory() as db:
            job = db.query(EvaluationJobModel).filter(EvaluationJobModel.status == "queued").order_by(EvaluationJobModel.created_at).with_for_update(skip_locked=True).first()
            if not job:
                return None
            job.status = "preflight"; job.worker_id = self.worker_id; job.started_at = job.started_at or datetime.now(UTC); job.heartbeat_at = datetime.now(UTC)
            db.commit(); return job.id

    def _cancel_requested(self, job_id: str) -> bool:
        with self.session_factory() as db:
            job = db.get(EvaluationJobModel, job_id)
            return bool(job.cancel_requested_at)

    def _progress(self, job_id: str, current: str, completed: int, failed: int, percentage: float) -> None:
        with self.session_factory() as db:
            job = db.get(EvaluationJobModel, job_id)
            job.progress_json = json.dumps({"current_scenario": current, "completed_count": completed, "failed_count": failed, "progress_percentage": max(0, min(100, percentage))})
            job.heartbeat_at = datetime.now(UTC); db.commit()
