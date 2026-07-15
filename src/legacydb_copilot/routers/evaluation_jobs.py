from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from legacydb_copilot.db.models import UserModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import get_current_user
from legacydb_copilot.security.access_control import require_workspace_access
from legacydb_copilot.services.evaluation_job_service import EvaluationJobRequest, EvaluationJobService, public_job

router = APIRouter(prefix="/evaluation/runs", tags=["evaluation-jobs"])


class EvaluationRunCreate(BaseModel):
    organization_id: str
    workspace_id: str
    run_type: Literal["pilot_smoke", "selected_scenarios"]
    run_name: str = Field(min_length=1, max_length=200)
    scenario_ids: list[str] = Field(default_factory=list, max_length=25)
    concurrency: int = Field(default=1, ge=1, le=5)
    timeout_seconds: int = Field(default=600, ge=30, le=1800)
    judge_model: str = Field(min_length=1, max_length=160)
    estimated_cost_usd: float = Field(default=0, ge=0, le=100)
    confirmed: bool
    parent_run_id: str | None = None

    @model_validator(mode="after")
    def validate_scenario_selection(self):
        if self.run_type == "selected_scenarios" and not self.scenario_ids:
            raise ValueError("Selected-scenario runs require at least one scenario")
        return self


def _response(db: Session, job):
    user = db.get(UserModel, job.requested_by_id)
    return public_job(job, user.email if user else "unknown")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_run(payload: EvaluationRunCreate, db: Annotated[Session, Depends(get_db_session)], user=Depends(get_current_user)):
    if payload.organization_id != user.organization_id and user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    require_workspace_access(db, user, payload.workspace_id, action="evaluation")
    job = EvaluationJobService(db, user).create(EvaluationJobRequest(**payload.model_dump()))
    return _response(db, job)


@router.get("/{job_id}")
def get_run(job_id: str, db: Annotated[Session, Depends(get_db_session)], user=Depends(get_current_user)):
    job = EvaluationJobService(db, user).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    require_workspace_access(db, user, job.workspace_id, action="read")
    return _response(db, job)
