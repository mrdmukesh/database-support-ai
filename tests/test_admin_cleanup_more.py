from __future__ import annotations

import os
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import legacydb_copilot.routers.admin as admin_router
from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.db.models import (
    DatabaseConnectionModel,
    WorkspaceModel,
    WorkspaceMembershipModel,
    InvestigationModel,
    DocumentModel,
    UserModel,
)


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


def test_preview_does_not_modify_data(client: TestClient):
    org = client.post("/organizations", json={"name": "P", "slug": "p"}).json()
    client.post(
        "/auth/signup",
        json={
            "organization_id": org["id"],
            "email": "admin2@example.com",
            "password": "StrongPass123!",
            "full_name": "Admin2",
            "role": "organization_admin",
            "consents": [
                "terms_of_service",
                "privacy_policy",
                "document_processing",
                "ai_verification_required",
            ],
            "ip_address": "127.0.0.1",
        },
    )
    headers = _auth_headers(client, "admin2@example.com")
    ws = client.post("/workspaces", json={"organization_id": org["id"], "name": "W", "slug": "w"}, headers=headers).json()
    client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": ws["id"],
            "engine": "postgresql",
            "name": "C",
            "environment_type": "test",
            "host": "db",
            "database_name": "d",
            "secret_ref": "secret://x",
        },
        headers=headers,
    )

    before = client.get(f"/admin/summary", headers=headers).json()
    preview = client.post(f"/admin/test-data-cleanup/preview?organization_id={org['id']}", headers=headers)
    assert preview.status_code == 200
    after = client.get(f"/admin/summary", headers=headers).json()
    assert before == after


def test_non_admin_cannot_execute(client: TestClient):
    org = client.post("/organizations", json={"name": "NA", "slug": "na"}).json()
    signup = client.post(
        "/auth/signup",
        json={
            "organization_id": org["id"],
            "email": "user@example.com",
            "password": "StrongPass123!",
            "full_name": "User",
            "role": "read_only_user",
            "consents": [
                "terms_of_service",
                "privacy_policy",
                "document_processing",
                "ai_verification_required",
            ],
            "ip_address": "127.0.0.1",
        },
    ).json()
    headers = _auth_headers(client, "user@example.com")
    os.environ.pop("ALLOW_TEST_DATA_CLEANUP", None)
    resp = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json={"confirmation": "DELETE TEST APP DATA"}, headers=headers)
    assert resp.status_code == 403


def test_env_guard_and_confirmation(client: TestClient):
    org = client.post("/organizations", json={"name": "EG", "slug": "eg"}).json()
    client.post(
        "/auth/signup",
        json={
            "organization_id": org["id"],
            "email": "admin3@example.com",
            "password": "StrongPass123!",
            "full_name": "Admin3",
            "role": "organization_admin",
            "consents": [
                "terms_of_service",
                "privacy_policy",
                "document_processing",
                "ai_verification_required",
            ],
            "ip_address": "127.0.0.1",
        },
    )
    headers = _auth_headers(client, "admin3@example.com")
    # guard blocks when not set
    os.environ.pop("ALLOW_TEST_DATA_CLEANUP", None)
    resp = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json={"confirmation": "DELETE TEST APP DATA"}, headers=headers)
    assert resp.status_code == 403
    # wrong confirmation
    os.environ["ALLOW_TEST_DATA_CLEANUP"] = "true"
    resp2 = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json={"confirmation": "WRONG"}, headers=headers)
    assert resp2.status_code == 400


def test_execute_idempotent_and_users_preserved(client: TestClient):
    org = client.post("/organizations", json={"name": "ID", "slug": "id"}).json()
    client.post(
        "/auth/signup",
        json={
            "organization_id": org["id"],
            "email": "admin4@example.com",
            "password": "StrongPass123!",
            "full_name": "Admin4",
            "role": "organization_admin",
            "consents": [
                "terms_of_service",
                "privacy_policy",
                "document_processing",
                "ai_verification_required",
            ],
            "ip_address": "127.0.0.1",
        },
    )
    client.post(
        "/auth/signup",
        json={
            "organization_id": org["id"],
            "email": "user2@example.com",
            "password": "StrongPass123!",
            "full_name": "User2",
            "role": "organization_editor",
            "consents": [
                "terms_of_service",
                "privacy_policy",
                "document_processing",
                "ai_verification_required",
            ],
            "ip_address": "127.0.0.1",
        },
    )
    headers = _auth_headers(client, "admin4@example.com")
    ws = client.post("/workspaces", json={"organization_id": org["id"], "name": "W", "slug": "w"}, headers=headers).json()
    client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": ws["id"],
            "engine": "postgresql",
            "name": "C",
            "environment_type": "test",
            "host": "db",
            "database_name": "d",
            "secret_ref": "secret://x",
        },
        headers=headers,
    )
    os.environ["ALLOW_TEST_DATA_CLEANUP"] = "true"
    resp = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json={"confirmation": "DELETE TEST APP DATA", "keep_default_workspace": True}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["physical_databases_deleted"] == 0
    assert body["summary"]["users_deleted"] == 0
    # run again -> idempotent
    resp2 = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json={"confirmation": "DELETE TEST APP DATA", "keep_default_workspace": True}, headers=headers)
    assert resp2.status_code == 200
    body2 = resp2.json()
    # second run should not delete additional users
    assert body2["summary"]["users_deleted"] == 0


def test_rollback_on_failure_restores_state(client, monkeypatch):
    org = client.post("/organizations", json={"name": "RB", "slug": "rb"}).json()
    client.post(
        "/auth/signup",
        json={
            "organization_id": org["id"],
            "email": "admin5@example.com",
            "password": "StrongPass123!",
            "full_name": "Admin5",
            "role": "organization_admin",
            "consents": [
                "terms_of_service",
                "privacy_policy",
                "document_processing",
                "ai_verification_required",
            ],
            "ip_address": "127.0.0.1",
        },
    )
    headers = _auth_headers(client, "admin5@example.com")
    ws = client.post("/workspaces", json={"organization_id": org["id"], "name": "W", "slug": "w"}, headers=headers).json()
    client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": ws["id"],
            "engine": "postgresql",
            "name": "C",
            "environment_type": "test",
            "host": "db",
            "database_name": "d",
            "secret_ref": "secret://x",
        },
        headers=headers,
    )
    # monkeypatch the audit to throw to force rollback
    def _boom(*args, **kwargs):
        raise Exception("boom")

    monkeypatch.setattr(admin_router, "record_audit_event", _boom)
    os.environ["ALLOW_TEST_DATA_CLEANUP"] = "true"
    resp = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json={"confirmation": "DELETE TEST APP DATA"}, headers=headers)
    assert resp.status_code == 500
    # ensure connection still exists
    conns = client.get(f"/databases/connections?organization_id={org['id']}", headers=headers).json()
    assert len(conns) == 1


def test_no_forbidden_external_delete_calls_present():
    path = "src/legacydb_copilot/routers/admin.py"
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()
    forbidden = ["DROP DATABASE", "az sql db delete", "azure", "delete_management_client", "SqlManagementClient"]
    for f in forbidden:
        assert f.lower() not in content.lower()
