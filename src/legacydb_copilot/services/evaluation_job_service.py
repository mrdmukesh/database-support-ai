from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role
from legacydb_copilot.db.models import EvaluationJobModel, UserModel


ACTIVE_STATUSES = ("queued", "preflight", "running")


@dataclass(frozen=True)
class EvaluationJobRequest:
    organization_id: str
    workspace_id: str
    run_type: str
    run_name: str
    scenario_ids: list[str]
    concurrency: int
    timeout_seconds: int
    judge_model: str
    estimated_cost_usd: float
    confirmed: bool
    parent_run_id: str | None = None


def may_manage_evaluations(user: UserModel) -> bool:
    configured = {item.strip() for item in os.getenv("EVALUATION_ADMIN_USER_IDS", "").split(",") if item.strip()}
    return user.role in {Role.SUPER_ADMIN.value, Role.ORG_ADMIN.value} or user.id in configured


class EvaluationJobService:
    def __init__(self, db: Session, user: UserModel):
        self.db = db
        self.user = user

    def create(self, request: EvaluationJobRequest) -> EvaluationJobModel:
        if not may_manage_evaluations(self.user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evaluation administrator permission required")
        if self.user.role != Role.SUPER_ADMIN.value and request.organization_id != self.user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied")
        if not request.confirmed:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Evaluation cost and immutable snapshot confirmation is required")
        workspace_limit = max(1, int(os.getenv("EVALUATION_WORKSPACE_CONCURRENCY_LIMIT", "1")))
        global_limit = max(workspace_limit, int(os.getenv("EVALUATION_GLOBAL_CONCURRENCY_LIMIT", "2")))
        global_active = self.db.query(EvaluationJobModel).filter(EvaluationJobModel.status.in_(ACTIVE_STATUSES)).count()
        if global_active >= global_limit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The global evaluation concurrency limit is active")
        workspace_active = self.db.query(EvaluationJobModel).filter(
            EvaluationJobModel.workspace_id == request.workspace_id,
            EvaluationJobModel.status.in_(ACTIVE_STATUSES),
        ).count()
        if workspace_active >= workspace_limit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An evaluation is already active for this workspace")
        configuration = {
            "concurrency": request.concurrency,
            "timeout_seconds": request.timeout_seconds,
            "judge_model": request.judge_model,
        }
        job = EvaluationJobModel(
            organization_id=request.organization_id,
            workspace_id=request.workspace_id,
            requested_by_id=self.user.id,
            parent_run_id=request.parent_run_id,
            run_name=request.run_name,
            run_type=request.run_type,
            status="queued",
            configuration_json=json.dumps(configuration),
            selected_scenarios_json=json.dumps(request.scenario_ids),
            progress_json=json.dumps({"current_scenario": None, "completed_count": 0, "failed_count": 0, "progress_percentage": 0}),
            model=request.judge_model,
            estimated_cost_usd=request.estimated_cost_usd,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: str) -> EvaluationJobModel | None:
        job = self.db.get(EvaluationJobModel, job_id)
        if job is None:
            return None
        if self.user.role != Role.SUPER_ADMIN.value and job.organization_id != self.user.organization_id:
            return None
        return job

    def list(self, workspace_id: str | None = None) -> list[EvaluationJobModel]:
        query = self.db.query(EvaluationJobModel)
        if self.user.role != Role.SUPER_ADMIN.value:
            query = query.filter(EvaluationJobModel.organization_id == self.user.organization_id)
        if workspace_id:
            query = query.filter(EvaluationJobModel.workspace_id == workspace_id)
        return query.order_by(EvaluationJobModel.created_at.desc()).all()

    def cancel(self, job_id: str) -> EvaluationJobModel | None:
        if not may_manage_evaluations(self.user):
            raise HTTPException(status_code=403, detail="Evaluation administrator permission required")
        job = self.get(job_id)
        if job is None:
            return None
        if job.status not in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail="Only active evaluation jobs can be cancelled")
        job.cancel_requested_at = datetime.now(UTC)
        if job.status == "queued":
            job.status = "cancelled"; job.completed_at = datetime.now(UTC)
        self.db.commit(); self.db.refresh(job); return job

    def retry(self, job_id: str) -> EvaluationJobModel | None:
        if not may_manage_evaluations(self.user):
            raise HTTPException(status_code=403, detail="Evaluation administrator permission required")
        original = self.get(job_id)
        if original is None:
            return None
        if original.status in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail="Active evaluations cannot be retried")
        config = json.loads(original.configuration_json or "{}")
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        return self.create(EvaluationJobRequest(
            organization_id=original.organization_id, workspace_id=original.workspace_id,
            run_type=original.run_type, run_name=f"{original.run_name}-rerun-{stamp}",
            scenario_ids=json.loads(original.selected_scenarios_json or "[]"),
            concurrency=int(config.get("concurrency") or 1), timeout_seconds=int(config.get("timeout_seconds") or 600),
            judge_model=original.model, estimated_cost_usd=float(original.estimated_cost_usd or 0),
            confirmed=True, parent_run_id=original.evaluation_run_id or original.id,
        ))


def public_job(job: EvaluationJobModel, requested_by_email: str) -> dict[str, Any]:
    configuration = json.loads(job.configuration_json or "{}")
    progress = json.loads(job.progress_json or "{}")
    return {
        "id": job.id, "organization_id": job.organization_id, "workspace_id": job.workspace_id,
        "evaluation_run_id": job.evaluation_run_id, "parent_run_id": job.parent_run_id,
        "run_name": job.run_name, "run_type": job.run_type, "status": job.status,
        "scenario_ids": json.loads(job.selected_scenarios_json or "[]"),
        "concurrency": configuration.get("concurrency"), "timeout_seconds": configuration.get("timeout_seconds"),
        "judge_model": job.model, "judge_version": job.judge_version, "prompt_version": job.prompt_version,
        "estimated_cost_usd": float(job.estimated_cost_usd or 0), "actual_cost_usd": float(job.actual_cost_usd or 0),
        "requested_by_id": job.requested_by_id, "requested_by_email": requested_by_email,
        "created_at": job.created_at, "started_at": job.started_at, "completed_at": job.completed_at,
        **progress,
    }
