from __future__ import annotations

import os
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.session import get_db_session


@pytest.fixture
def client() -> TestClient:
    app = create_fastapi_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_db_session():
        db: Session = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


def _auth_headers(client: TestClient, email: str, password: str = "StrongPass123!") -> dict[str, str]:
    login_response = client.post("/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    session = login_response.json()
    return {"Authorization": f"{session['token_type']} {session['access_token']}"}


def test_preview_and_execute_cleanup_flow(client: TestClient) -> None:
    # create organization and admin user
    org = client.post("/organizations", json={"name": "ACME", "slug": "acme"}).json()
    signup = client.post(
        "/auth/signup",
        json={
            "organization_id": org["id"],
            "email": "admin@example.com",
            "password": "StrongPass123!",
            "full_name": "Admin",
            "role": "organization_admin",
            "consents": [
                "terms_of_service",
                "privacy_policy",
                "document_processing",
                "ai_verification_required",
            ],
            "ip_address": "127.0.0.1",
        },
    ).json()
    headers = _auth_headers(client, "admin@example.com")

    # create workspace and connection
    ws = client.post("/workspaces", json={"organization_id": org["id"], "name": "W", "slug": "w"}, headers=headers).json()
    conn = client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": ws["id"],
            "engine": "postgresql",
            "name": "Test DB",
            "environment_type": "test",
            "host": "db",
            "database_name": "test",
            "secret_ref": "secret://x",
        },
        headers=headers,
    ).json()

    # preview
    preview = client.post(f"/admin/test-data-cleanup/preview?organization_id={org['id']}", headers=headers)
    assert preview.status_code == 200
    body = preview.json()
    assert body["counts"]["connections"] == 1

    # execute without env guard should be blocked
    payload = {"confirmation": "DELETE TEST APP DATA", "keep_default_workspace": True}
    resp = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json=payload, headers=headers)
    assert resp.status_code == 403

    # enable env guard and execute
    os.environ["ALLOW_TEST_DATA_CLEANUP"] = "true"
    resp2 = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json=payload, headers=headers)
    assert resp2.status_code == 200
    out = resp2.json()
    assert out["before"]["connections"] == 1
    assert out["after"]["connections"] == 0
