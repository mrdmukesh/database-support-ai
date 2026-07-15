from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import EvaluationJobModel, OrganizationModel, UserModel, WorkspaceModel
from legacydb_copilot.services.evaluation_job_worker import EvaluationJobWorker


class Executor:
    def __init__(self, *, preflight=True):
        self.preflight_passes = preflight
        self.executed = []

    def preflight(self, _job):
        return {"passed": self.preflight_passes, "checks": [{"name": "safety", "status": "PASS" if self.preflight_passes else "FAIL"}]}

    def execute(self, job, should_cancel, update):
        self.executed.append(job.id)
        update("scenario-1", 1, 0, 50)
        if should_cancel():
            return {"cancelled": True}
        update("scenario-2", 2, 0, 100)
        return {"run_id": "RUN-1", "completed": 2, "failed": 0, "actual_cost_usd": 0.02}


def database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = OrganizationModel(name="Org", slug="org")
        db.add(org); db.flush()
        user = UserModel(organization_id=org.id, email="admin@example.com", role="organization_admin")
        workspace = WorkspaceModel(organization_id=org.id, name="Workspace", slug="workspace")
        db.add_all([user, workspace]); db.flush()
        job = EvaluationJobModel(organization_id=org.id, workspace_id=workspace.id, requested_by_id=user.id, run_name="pilot", run_type="pilot_smoke", status="queued", configuration_json='{"concurrency":1}', selected_scenarios_json="[]", progress_json="{}", model="judge")
        db.add(job); db.commit()
        return engine, job.id


def test_worker_progresses_job_to_completed() -> None:
    engine, job_id = database(); executor = Executor()
    worker = EvaluationJobWorker(lambda: Session(engine), executor, worker_id="worker-1")
    assert worker.run_once()
    with Session(engine) as db:
        job = db.get(EvaluationJobModel, job_id)
        assert job.status == "completed" and job.evaluation_run_id == "RUN-1"
        assert float(job.actual_cost_usd) == 0.02 and job.completed_at is not None


def test_failed_preflight_blocks_execution() -> None:
    engine, job_id = database(); executor = Executor(preflight=False)
    EvaluationJobWorker(lambda: Session(engine), executor, worker_id="worker-1").run_once()
    with Session(engine) as db:
        assert db.get(EvaluationJobModel, job_id).status == "failed"
    assert executor.executed == []


def test_cancellation_is_honored_between_scenarios() -> None:
    engine, job_id = database(); executor = Executor()
    with Session(engine) as db:
        job = db.get(EvaluationJobModel, job_id); job.cancel_requested_at = datetime.now(UTC); db.commit()
    EvaluationJobWorker(lambda: Session(engine), executor, worker_id="worker-1").run_once()
    with Session(engine) as db:
        assert db.get(EvaluationJobModel, job_id).status == "cancelled"


def test_restart_recovery_requeues_stale_claim() -> None:
    engine, job_id = database()
    with Session(engine) as db:
        job = db.get(EvaluationJobModel, job_id); job.status = "running"; job.worker_id = "dead"; job.heartbeat_at = datetime.now(UTC) - timedelta(hours=1); db.commit()
    worker = EvaluationJobWorker(lambda: Session(engine), Executor(), worker_id="worker-2", stale_after_seconds=60)
    assert worker.recover_stale_jobs() == 1
    with Session(engine) as db:
        job = db.get(EvaluationJobModel, job_id); assert job.status == "queued" and job.worker_id == ""
