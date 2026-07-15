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


@router.get("")
def list_runs(db: Annotated[Session, Depends(get_db_session)], user=Depends(get_current_user), workspace_id: str | None = None):
    jobs = EvaluationJobService(db, user).list(workspace_id)
    return [_response(db, job) for job in jobs]


@router.get("/{job_id}")
def get_run(job_id: str, db: Annotated[Session, Depends(get_db_session)], user=Depends(get_current_user)):
    job = EvaluationJobService(db, user).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    require_workspace_access(db, user, job.workspace_id, action="read")
    return _response(db, job)


@router.post("/{job_id}/cancel")
def cancel_run(job_id: str, db: Annotated[Session, Depends(get_db_session)], user=Depends(get_current_user)):
    job = EvaluationJobService(db, user).cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    return _response(db, job)


@router.post("/{job_id}/retry", status_code=status.HTTP_201_CREATED)
def retry_run(job_id: str, db: Annotated[Session, Depends(get_db_session)], user=Depends(get_current_user)):
    job = EvaluationJobService(db, user).retry(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    return _response(db, job)


@router.get("/{job_id}/reports")
def run_reports(job_id: str, db: Annotated[Session, Depends(get_db_session)], user=Depends(get_current_user)):
    job = EvaluationJobService(db, user).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    require_workspace_access(db, user, job.workspace_id, action="read")
    if not job.evaluation_run_id:
        return []
    from legacydb_copilot.services.evaluation_dashboard_service import EvaluationDashboardService
    rows = EvaluationDashboardService(db, organization_id=None if user.role == "super_admin" else user.organization_id).scenarios(job.evaluation_run_id)
    return [{"result_id": row["result_id"], "scenario_id": row["scenario_id"], "status": row["execution_status"], "report_url": f"/react/app/evaluation/scenarios/{row['result_id']}"} for row in rows]


@router.post("/{job_id}/regenerate-reports")
def regenerate_reports(job_id: str, db: Annotated[Session, Depends(get_db_session)], user=Depends(get_current_user)):
    from evaluation.framework.models import EvaluationScenarioExecutionModel
    from legacydb_copilot.db.models import InvestigationModel
    from legacydb_copilot.routers.chat import _regenerate_report_with_verification
    from legacydb_copilot.services.evaluation_job_service import may_manage_evaluations
    if not may_manage_evaluations(user):
        raise HTTPException(status_code=403, detail="Evaluation administrator permission required")
    job = EvaluationJobService(db, user).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    if not job.evaluation_run_id:
        raise HTTPException(status_code=409, detail="Evaluation job has no completed run")
    executions = db.query(EvaluationScenarioExecutionModel).filter(EvaluationScenarioExecutionModel.evaluation_run_id == job.evaluation_run_id).all()
    reports = []
    for execution in executions:
        investigation = db.query(InvestigationModel).filter(InvestigationModel.id == execution.investigation_id, InvestigationModel.organization_id == job.organization_id, InvestigationModel.workspace_id == job.workspace_id).one_or_none()
        if not investigation:
            reports.append({"scenario_id": execution.scenario_id, "status": "unavailable"}); continue
        try:
            links = _regenerate_report_with_verification(db, investigation)
            reports.append({"scenario_id": execution.scenario_id, "status": "completed", "links": links or {}})
        except Exception:
            reports.append({"scenario_id": execution.scenario_id, "status": "failed", "links": {"json": f"/evaluation-dashboard/scenarios/{execution.id}"}})
    db.commit()
    overall = "completed" if reports and all(item["status"] == "completed" for item in reports) else "partially_completed"
    return {"status": overall, "reports": reports}
