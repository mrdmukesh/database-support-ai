from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role
from legacydb_copilot.db.models import UserModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.evaluation_dashboard_service import EvaluationDashboardService
from legacydb_copilot.services.evaluation_job_service import may_manage_evaluations

router = APIRouter(prefix="/evaluation-dashboard", tags=["evaluation-dashboard"])
DashboardUser = Annotated[UserModel, Depends(require_permission("admin:read"))]


class DeleteRunsRequest(BaseModel):
    run_ids: list[str] = Field(min_length=1, max_length=50)


def service(db: Session, user: UserModel) -> EvaluationDashboardService:
    organization_id = None if user.role == Role.SUPER_ADMIN.value else user.organization_id
    return EvaluationDashboardService(db, organization_id=organization_id)


@router.get("/runs")
def runs(db: Annotated[Session, Depends(get_db_session)], user: DashboardUser):
    return service(db, user).runs()


@router.get("/runs/{run_id}/summary")
def summary(run_id: str, db: Annotated[Session, Depends(get_db_session)], user: DashboardUser):
    dashboard = service(db, user)
    if not any(run["id"] == run_id for run in dashboard.runs()):
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return dashboard.summary(run_id)


@router.get("/runs/{run_id}/scenarios")
def scenarios(run_id: str, db: Annotated[Session, Depends(get_db_session)], user: DashboardUser):
    return service(db, user).scenarios(run_id)


@router.get("/scenarios/{result_id}")
def scenario(result_id: str, db: Annotated[Session, Depends(get_db_session)], user: DashboardUser):
    result = service(db, user).scenario_detail(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Evaluation result not found")
    return result


@router.get("/runs/{run_id}/human-reviews")
def human_reviews(run_id: str, db: Annotated[Session, Depends(get_db_session)], user: DashboardUser):
    return service(db, user).human_reviews(run_id)


@router.get("/compare")
def compare(baseline_run_id: str, candidate_run_id: str, db: Annotated[Session, Depends(get_db_session)], user: DashboardUser):
    dashboard = service(db, user)
    available = {run["id"] for run in dashboard.runs()}
    if baseline_run_id not in available or candidate_run_id not in available:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return dashboard.compare(baseline_run_id, candidate_run_id)


@router.post("/runs/delete")
def delete_runs(payload: DeleteRunsRequest, db: Annotated[Session, Depends(get_db_session)], user: DashboardUser):
    if not may_manage_evaluations(user):
        raise HTTPException(status_code=403, detail="Evaluation administrator permission required")
    result = service(db, user).delete_runs(payload.run_ids)
    for row in result["deleted"]:
        record_audit_event(
            db,
            organization_id=user.organization_id,
            user_id=user.id,
            action="evaluation.run.delete",
            resource_type="evaluation_run",
            resource_id=row["id"],
            metadata={"run_name": row["name"], "requested_count": result["requested_count"]},
        )
    for row in result["protected"]:
        record_audit_event(
            db,
            organization_id=user.organization_id,
            user_id=user.id,
            action="evaluation.run.delete_blocked",
            resource_type="evaluation_run",
            resource_id=row["id"],
            status="blocked",
            metadata={"run_name": row["name"], "reason": row["reason"]},
        )
    return result
