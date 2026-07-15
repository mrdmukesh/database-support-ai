from __future__ import annotations

import io
import json
from urllib import error

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from evaluation.runners.public_api import PublicInvestigationAPI
from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.security import decode_access_token


@pytest.fixture
def service_client(monkeypatch: pytest.MonkeyPatch):
    app = create_fastapi_app()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_db_session():
        db: Session = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    org = client.post("/organizations", json={"name": "Evaluation Org", "slug": "evaluation-org"}).json()
    user = client.post("/auth/signup", json={
        "organization_id": org["id"], "email": "evaluation@example.com", "password": "StrongPass123!",
        "full_name": "Evaluation Worker", "role": "organization_admin",
        "consents": ["terms_of_service", "privacy_policy", "document_processing", "ai_verification_required"],
        "ip_address": "127.0.0.1",
    }).json()
    login = client.post("/auth/login", json={"email": "evaluation@example.com", "password": "StrongPass123!"}).json()
    workspace = client.post("/workspaces", headers={"Authorization": f"Bearer {login['access_token']}"}, json={
        "organization_id": org["id"], "name": "Evaluation", "slug": "evaluation",
    }).json()
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("EVALUATION_SERVICE_CLIENT_ID", "worker-client")
    monkeypatch.setenv("EVALUATION_SERVICE_CLIENT_SECRET", "worker-secret")
    monkeypatch.setenv("EVALUATION_SERVICE_USER_ID", user["id"])
    monkeypatch.setenv("EVALUATION_SERVICE_ORGANIZATION_ID", org["id"])
    monkeypatch.setenv("EVALUATION_SERVICE_WORKSPACE_ID", workspace["id"])
    return client, {"user_id": user["id"], "organization_id": org["id"]}


def test_service_token_is_tenant_bound(service_client) -> None:
    client, expected = service_client
    response = client.post("/auth/evaluation-token", json={"client_id": "worker-client", "client_secret": "worker-secret"})
    assert response.status_code == 200
    claims = decode_access_token(response.json()["access_token"], secret="test-jwt-secret")
    assert claims["sub"] == expected["user_id"]
    assert claims["organization_id"] == expected["organization_id"]
    assert response.json()["expires_in"] == 900


def test_service_token_rejects_bad_secret(service_client) -> None:
    client, _ = service_client
    assert client.post("/auth/evaluation-token", json={"client_id": "worker-client", "client_secret": "wrong"}).status_code == 401


def test_service_token_rejects_unauthorized_workspace(service_client, monkeypatch) -> None:
    client, _ = service_client
    monkeypatch.setenv("EVALUATION_SERVICE_WORKSPACE_ID", "missing-workspace")
    assert client.post("/auth/evaluation-token", json={"client_id": "worker-client", "client_secret": "worker-secret"}).status_code == 403


def test_public_api_refreshes_once_after_401(monkeypatch: pytest.MonkeyPatch) -> None:
    issued = iter(["expired-token", "fresh-token"])
    seen: list[str] = []

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return json.dumps({"id": "INV-1"}).encode()

    def urlopen(call, timeout):
        seen.append(call.headers["Authorization"])
        if len(seen) == 1:
            raise error.HTTPError(call.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))
        return Response()

    monkeypatch.setattr("evaluation.runners.public_api.request.urlopen", urlopen)
    body, status = PublicInvestigationAPI("https://example.test", token_provider=lambda: next(issued)).submit({"question": "test"})
    assert (body["id"], status) == ("INV-1", 200)
    assert seen == ["Bearer expired-token", "Bearer fresh-token"]
