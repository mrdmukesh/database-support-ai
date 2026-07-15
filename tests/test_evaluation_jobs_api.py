from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.db.base import Base
from legacydb_copilot.db import models as application_models  # noqa: F401
from legacydb_copilot.db.session import get_db_session


@pytest.fixture
def jobs_client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_fastapi_app()

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = override
    return TestClient(app)


def account(client: TestClient, suffix: str, role: str = "organization_admin"):
    org = client.post("/organizations", json={"name": f"Jobs {suffix}", "slug": f"jobs-{suffix}"}).json()
    client.post("/auth/signup", json={
        "organization_id": org["id"], "email": f"{suffix}@example.com", "password": "StrongPass123!",
        "full_name": "Evaluator", "role": role,
        "consents": ["terms_of_service", "privacy_policy", "document_processing", "ai_verification_required"],
        "ip_address": "127.0.0.1",
    })
    token = client.post("/auth/login", json={"email": f"{suffix}@example.com", "password": "StrongPass123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    workspace = (
        client.post("/workspaces", headers=headers, json={"organization_id": org["id"], "name": "Evaluation", "slug": "evaluation"}).json()
        if role in {"organization_admin", "super_admin"}
        else {"id": "not-created"}
    )
    return org, workspace, headers


def payload(org, workspace, **overrides):
    value = {
        "organization_id": org["id"], "workspace_id": workspace["id"], "run_type": "pilot_smoke",
        "run_name": "secure-pilot", "scenario_ids": [], "concurrency": 1, "timeout_seconds": 600,
        "judge_model": "gpt-4.1-mini", "estimated_cost_usd": 0.05, "confirmed": True,
    }
    value.update(overrides)
    return value


def test_authorized_admin_can_enqueue_sanitized_job(jobs_client: TestClient) -> None:
    org, workspace, headers = account(jobs_client, "admin")
    response = jobs_client.post("/evaluation/runs", headers=headers, json=payload(org, workspace))
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued" and body["requested_by_email"] == "admin@example.com"
    assert "token" not in str(body).lower() and "connection_string" not in str(body).lower()


def test_unauthorized_user_cannot_enqueue_job(jobs_client: TestClient) -> None:
    org, workspace, _ = account(jobs_client, "owner")
    _, _, reader = account(jobs_client, "reader", role="read_only_user")
    response = jobs_client.post("/evaluation/runs", headers=reader, json=payload(org, workspace))
    assert response.status_code == 403


def test_cross_tenant_job_is_rejected(jobs_client: TestClient) -> None:
    org, workspace, _ = account(jobs_client, "tenant-a")
    _, _, other = account(jobs_client, "tenant-b")
    assert jobs_client.post("/evaluation/runs", headers=other, json=payload(org, workspace)).status_code == 403


def test_duplicate_active_workspace_run_is_rejected(jobs_client: TestClient) -> None:
    org, workspace, headers = account(jobs_client, "duplicate")
    assert jobs_client.post("/evaluation/runs", headers=headers, json=payload(org, workspace)).status_code == 201
    response = jobs_client.post("/evaluation/runs", headers=headers, json=payload(org, workspace, run_name="second"))
    assert response.status_code == 409


def test_confirmation_and_safe_configuration_are_required(jobs_client: TestClient) -> None:
    org, workspace, headers = account(jobs_client, "safety")
    assert jobs_client.post("/evaluation/runs", headers=headers, json=payload(org, workspace, confirmed=False)).status_code == 422
    assert jobs_client.post("/evaluation/runs", headers=headers, json=payload(org, workspace, concurrency=0)).status_code == 422
    assert jobs_client.post("/evaluation/runs", headers=headers, json=payload(org, workspace, run_type="selected_scenarios", scenario_ids=[])).status_code == 422


def test_job_reads_are_tenant_isolated(jobs_client: TestClient) -> None:
    org, workspace, headers = account(jobs_client, "visible")
    job = jobs_client.post("/evaluation/runs", headers=headers, json=payload(org, workspace)).json()
    _, _, other = account(jobs_client, "hidden")
    assert jobs_client.get(f"/evaluation/runs/{job['id']}", headers=headers).status_code == 200
    assert jobs_client.get(f"/evaluation/runs/{job['id']}", headers=other).status_code == 404
