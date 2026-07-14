from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from evaluation.framework.models import EvaluationRunModel, EvaluationScenarioExecutionModel, TestScenarioModel as ScenarioRecord
from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.db.base import Base
from legacydb_copilot.db import models as application_models  # noqa: F401
from legacydb_copilot.db.session import get_db_session


@pytest.fixture
def dashboard_client():
    engine=create_engine("sqlite:///:memory:",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine); factory=sessionmaker(bind=engine,expire_on_commit=False)
    app=create_fastapi_app()
    def override():
        with factory() as db: yield db
    app.dependency_overrides[get_db_session]=override
    return TestClient(app),factory


def signup(client:TestClient, *, role="organization_admin", suffix="admin"):
    org=client.post("/organizations",json={"name":f"Eval {suffix}","slug":f"eval-{suffix}"}).json()
    client.post("/auth/signup",json={"organization_id":org["id"],"email":f"{suffix}@example.com","password":"StrongPass123!","full_name":"Evaluator","role":role,"consents":["terms_of_service","privacy_policy","document_processing","ai_verification_required"],"ip_address":"127.0.0.1"})
    token=client.post("/auth/login",json={"email":f"{suffix}@example.com","password":"StrongPass123!"}).json()["access_token"]
    return org["id"],{"Authorization":f"Bearer {token}"}


def test_dashboard_empty_state_api_and_rbac(dashboard_client):
    client,_=dashboard_client; _,headers=signup(client)
    assert client.get("/evaluation-dashboard/runs",headers=headers).json()==[]
    _,readonly=signup(client,role="read_only_user",suffix="reader")
    assert client.get("/evaluation-dashboard/runs",headers=readonly).status_code==403


def test_dashboard_returns_only_organization_results(dashboard_client):
    client,factory=dashboard_client; org_id,headers=signup(client)
    with factory() as db:
        run=EvaluationRunModel(application_commit="abc",application_version="0.1",status="created",configuration_json=json.dumps({"run_name":"pilot-v1"}),timing_cost_json="{}")
        scenario=ScenarioRecord(scenario_id="payroll-pilot-001",scenario_version=1,domain="payroll",database_engine="sqlserver",database_version="2022",category="root_cause",subcategory="missing",difficulty="medium",question="Why?",scripts_json="{}",expectations_json="{}",expected_response_type="confirmed_root_cause",active=True)
        db.add_all([run,scenario]);db.flush()
        db.add(EvaluationScenarioExecutionModel(evaluation_run_id=run.id,test_scenario_id=scenario.id,scenario_id=scenario.scenario_id,scenario_version=1,domain="payroll",database_version="2022",attempt=1,status="completed",investigation_id="INV-1",investigation_status="AI_ANSWERED",raw_request_json=json.dumps({"organization_id":org_id}),raw_response_json="{}",result_json=json.dumps({"answer":"Persisted answer"}),timing_json=json.dumps({"total_seconds":12}),usage_cost_json=json.dumps({"token_usage":{"total_tokens":20},"estimated_cost":.01}),errors_json="[]",retry_count=0,recovery_artifact=""));db.commit();run_id=run.id
    runs=client.get("/evaluation-dashboard/runs",headers=headers).json()
    assert runs[0]["name"]=="pilot-v1" and runs[0]["completed_count"]==1
    summary=client.get(f"/evaluation-dashboard/runs/{run_id}/summary",headers=headers).json()
    assert summary["scenario_count"]==1 and summary["deterministic_average"] is None
    rows=client.get(f"/evaluation-dashboard/runs/{run_id}/scenarios",headers=headers).json()
    detail=client.get(f"/evaluation-dashboard/scenarios/{rows[0]['result_id']}",headers=headers).json()
    assert detail["answer"]=="Persisted answer"
    assert "raw_request" not in detail and "expected_root_cause_concepts" not in detail
