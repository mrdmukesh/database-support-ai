from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role
from legacydb_copilot.db.models import UserModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.services.evaluation_dashboard_service import EvaluationDashboardService

router = APIRouter(prefix="/evaluation-dashboard", tags=["evaluation-dashboard"])
DashboardUser = Annotated[UserModel, Depends(require_permission("admin:read"))]


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
