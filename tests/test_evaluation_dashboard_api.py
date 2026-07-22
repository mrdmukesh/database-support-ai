from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from evaluation.framework.models import EvaluationAIJudgeScoreModel, EvaluationDeterministicScoreModel, EvaluationRunModel, EvaluationScenarioExecutionModel, TestScenarioModel as ScenarioRecord
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
        execution=EvaluationScenarioExecutionModel(evaluation_run_id=run.id,test_scenario_id=scenario.id,scenario_id=scenario.scenario_id,scenario_version=1,domain="payroll",database_version="2022",attempt=1,status="completed",investigation_id="INV-1",investigation_status="AI_ANSWERED",raw_request_json=json.dumps({"organization_id":org_id}),raw_response_json="{}",result_json=json.dumps({"answer":"Persisted answer"}),timing_json=json.dumps({"total_seconds":12}),usage_cost_json=json.dumps({"token_usage":{"total_tokens":20},"estimated_cost":.01}),errors_json="[]",retry_count=0,recovery_artifact="")
        db.add(execution);db.flush()
        deterministic=EvaluationDeterministicScoreModel(scenario_execution_id=execution.id,validation_version=1,root_cause_correctness=80,evidence_correctness=80,object_discovery=80,fix_correctness=80,citation_correctness=80,safety=80,completeness=80,unadjusted_score=80,final_score=80,classification="pass",critical_failure=False,details_json="{}")
        db.add(deterministic);db.flush()
        normalized={"root_cause_score":90,"evidence_score":85,"object_discovery_score":80,"fix_score":75,"citation_score":70,"safety_score":95,"completeness_score":85,"unsupported_claims":[],"missing_evidence":["lock evidence"],"incorrect_objects":[],"incorrect_entities":[],"critical_failure":False,"human_review_required":False,"explanation":"Evidence supports the answer."}
        db.add(EvaluationAIJudgeScoreModel(deterministic_score_id=deterministic.id,scenario_execution_id=execution.id,judge_version=1,judge_index=1,provider="openai",model="judge-model",prompt_version="v1",temperature=0,prompt_json="{}",prompt_hash="a"*64,raw_response_json="{}",normalized_result_json=json.dumps(normalized),weighted_score=84,deterministic_difference=4,input_tokens=100,output_tokens=50,duration_ms=1250,estimated_cost_usd=.002,retry_count=0,status="completed",error=""))
        db.commit();run_id=run.id
    runs=client.get("/evaluation-dashboard/runs",headers=headers).json()
    assert runs[0]["name"]=="pilot-v1" and runs[0]["completed_count"]==1
    summary=client.get(f"/evaluation-dashboard/runs/{run_id}/summary",headers=headers).json()
    assert summary["scenario_count"]==1 and summary["deterministic_average"]==80
    assert summary["ai_judge_average"]==84
    rows=client.get(f"/evaluation-dashboard/runs/{run_id}/scenarios",headers=headers).json()
    detail=client.get(f"/evaluation-dashboard/scenarios/{rows[0]['result_id']}",headers=headers).json()
    assert detail["answer"]=="Persisted answer"
    assert detail["judge_report"]["invocations"][0]["model"]=="judge-model"
    assert detail["judge_report"]["invocations"][0]["result"]["missing_evidence"]==["lock evidence"]
    assert "raw_request" not in detail and "expected_root_cause_concepts" not in detail


def test_dashboard_delete_selected_runs_removes_only_unprotected_runs(dashboard_client):
    client, factory = dashboard_client
    org_id, headers = signup(client, suffix="delete")
    with factory() as db:
        scenario = ScenarioRecord(
            scenario_id="payroll-pilot-001",
            scenario_version=1,
            domain="payroll",
            database_engine="sqlserver",
            database_version="2022",
            category="root_cause",
            subcategory="missing",
            difficulty="medium",
            question="Why?",
            scripts_json="{}",
            expectations_json="{}",
            expected_response_type="confirmed_root_cause",
            active=True,
        )
        db.add(scenario)
        db.flush()

        deletable_run = EvaluationRunModel(
            application_commit="abc",
            application_version="0.1",
            status="completed",
            configuration_json=json.dumps({"run_name": "team-regression-1", "suite": "benchmark-100"}),
            timing_cost_json="{}",
        )
        protected_run = EvaluationRunModel(
            application_commit="def",
            application_version="0.1",
            status="completed",
            configuration_json=json.dumps({"run_name": "release benchmark 125", "protected_final_benchmark": True, "suite": "full-125"}),
            timing_cost_json="{}",
        )
        db.add_all([deletable_run, protected_run])
        db.flush()

        db.add_all(
            [
                EvaluationScenarioExecutionModel(
                    evaluation_run_id=deletable_run.id,
                    test_scenario_id=scenario.id,
                    scenario_id=scenario.scenario_id,
                    scenario_version=1,
                    domain="payroll",
                    database_version="2022",
                    attempt=1,
                    status="completed",
                    investigation_id="INV-A",
                    investigation_status="AI_ANSWERED",
                    raw_request_json=json.dumps({"organization_id": org_id}),
                    raw_response_json="{}",
                    result_json="{}",
                    timing_json="{}",
                    usage_cost_json="{}",
                    errors_json="[]",
                    retry_count=0,
                    recovery_artifact="",
                ),
                EvaluationScenarioExecutionModel(
                    evaluation_run_id=protected_run.id,
                    test_scenario_id=scenario.id,
                    scenario_id=scenario.scenario_id,
                    scenario_version=1,
                    domain="payroll",
                    database_version="2022",
                    attempt=2,
                    status="completed",
                    investigation_id="INV-B",
                    investigation_status="AI_ANSWERED",
                    raw_request_json=json.dumps({"organization_id": org_id}),
                    raw_response_json="{}",
                    result_json="{}",
                    timing_json="{}",
                    usage_cost_json="{}",
                    errors_json="[]",
                    retry_count=0,
                    recovery_artifact="",
                ),
            ]
        )
        db.commit()
        delete_id = deletable_run.id
        keep_id = protected_run.id

    response = client.post(
        "/evaluation-dashboard/runs/delete",
        headers=headers,
        json={"run_ids": [delete_id, keep_id]},
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["deleted"]] == [delete_id]
    assert [item["id"] for item in body["protected"]] == [keep_id]

    runs = client.get("/evaluation-dashboard/runs", headers=headers).json()
    run_ids = {row["id"] for row in runs}
    assert delete_id not in run_ids
    assert keep_id in run_ids


def test_dashboard_delete_requires_evaluation_admin_privilege(dashboard_client):
    client, factory = dashboard_client
    org_id, admin_headers = signup(client, suffix="admin-delete")
    _, reader_headers = signup(client, role="read_only_user", suffix="reader-delete")

    with factory() as db:
        run = EvaluationRunModel(
            application_commit="abc",
            application_version="0.1",
            status="completed",
            configuration_json=json.dumps({"run_name": "team-regression-2"}),
            timing_cost_json="{}",
        )
        scenario = ScenarioRecord(
            scenario_id="orders-pilot-001",
            scenario_version=1,
            domain="orders",
            database_engine="sqlserver",
            database_version="2022",
            category="root_cause",
            subcategory="missing",
            difficulty="medium",
            question="Why?",
            scripts_json="{}",
            expectations_json="{}",
            expected_response_type="confirmed_root_cause",
            active=True,
        )
        db.add_all([run, scenario])
        db.flush()
        db.add(
            EvaluationScenarioExecutionModel(
                evaluation_run_id=run.id,
                test_scenario_id=scenario.id,
                scenario_id=scenario.scenario_id,
                scenario_version=1,
                domain="orders",
                database_version="2022",
                attempt=1,
                status="completed",
                investigation_id="INV-R",
                investigation_status="AI_ANSWERED",
                raw_request_json=json.dumps({"organization_id": org_id}),
                raw_response_json="{}",
                result_json="{}",
                timing_json="{}",
                usage_cost_json="{}",
                errors_json="[]",
                retry_count=0,
                recovery_artifact="",
            )
        )
        db.commit()
        run_id = run.id

    forbidden = client.post("/evaluation-dashboard/runs/delete", headers=reader_headers, json={"run_ids": [run_id]})
    assert forbidden.status_code == 403

    allowed = client.post("/evaluation-dashboard/runs/delete", headers=admin_headers, json={"run_ids": [run_id]})
    assert allowed.status_code == 200
    assert [item["id"] for item in allowed.json()["deleted"]] == [run_id]
