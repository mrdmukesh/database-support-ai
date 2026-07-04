from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import AuditLogModel, InvestigationModel
from legacydb_copilot.db.session import get_db_session


@pytest.fixture
def enterprise_client(monkeypatch) -> tuple[TestClient, sessionmaker]:
    monkeypatch.setenv("FEATURE_ENTERPRISE_RBAC_ENABLED", "true")
    monkeypatch.setenv("FEATURE_AUDIT_LOGGING_ENABLED", "true")
    monkeypatch.setenv("FEATURE_KEYVAULT_SECRETS_ENABLED", "false")
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

    app = create_fastapi_app()
    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app), session_factory


def _create_user(client: TestClient, org_id: str, email: str) -> dict:
    response = client.post(
        "/auth/signup",
        json={
            "organization_id": org_id,
            "email": email,
            "password": "StrongPass123!",
            "full_name": email.split("@")[0],
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
    assert response.status_code == 201
    return response.json()


def _headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200
    body = response.json()
    return {"Authorization": f"{body['token_type']} {body['access_token']}"}


def _workspace(client: TestClient, org_id: str, headers: dict[str, str], name: str) -> dict:
    response = client.post(
        "/workspaces",
        json={"organization_id": org_id, "name": name, "slug": name.lower().replace(" ", "-")},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _enterprise_fixture(client: TestClient) -> tuple[dict, dict, dict, dict, dict, dict[str, str], dict[str, str]]:
    org = client.post("/organizations", json={"name": "Enterprise Corp", "slug": "enterprise-corp"}).json()
    user_a = _create_user(client, org["id"], "owner-a@example.com")
    user_b = _create_user(client, org["id"], "owner-b@example.com")
    headers_a = _headers(client, "owner-a@example.com")
    headers_b = _headers(client, "owner-b@example.com")
    workspace_a = _workspace(client, org["id"], headers_a, "Workspace A")
    workspace_b = _workspace(client, org["id"], headers_b, "Workspace B")
    return org, user_a, user_b, workspace_a, workspace_b, headers_a, headers_b


def test_user_cannot_access_another_workspace_report(
    enterprise_client: tuple[TestClient, sessionmaker],
    tmp_path: Path,
    monkeypatch,
) -> None:
    from legacydb_copilot.routers import reports as reports_router

    client, session_factory = enterprise_client
    org, _user_a, user_b, _workspace_a, workspace_b, headers_a, _headers_b = _enterprise_fixture(client)
    investigation_id = "INV-SECURITY-001"
    with session_factory() as db:
        db.add(
            InvestigationModel(
                id=investigation_id,
                organization_id=org["id"],
                workspace_id=workspace_b["id"],
                created_by_id=user_b["id"],
                user_question="Security report access test",
                detected_intent="TEST",
                ai_answer="answer",
                report_path=str(tmp_path / investigation_id),
                status="AI_ANSWERED",
            )
        )
        db.commit()

    monkeypatch.setattr(reports_router, "REPORT_HISTORY_DIR", tmp_path)
    response = client.get(f"/reports/{investigation_id}/investigation_report.pdf", headers=headers_a)

    assert response.status_code == 403


def test_user_cannot_access_another_workspace_database(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, _session_factory = enterprise_client
    org, _user_a, _user_b, _workspace_a, workspace_b, headers_a, headers_b = _enterprise_fixture(client)
    connection = client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": workspace_b["id"],
            "engine": "mysql",
            "name": "Workspace B DB",
            "connection_string": "mysql://root:secret@localhost:3306/demo",
        },
        headers=headers_b,
    ).json()

    response = client.get(f"/databases/connections/{connection['id']}/schema", headers=headers_a)

    assert response.status_code == 403


def test_audit_events_are_written_for_login_and_connection_create(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = enterprise_client
    org, _user_a, _user_b, workspace_a, _workspace_b, headers_a, _headers_b = _enterprise_fixture(client)
    response = client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": workspace_a["id"],
            "engine": "mysql",
            "name": "Audited DB",
            "connection_string": "mysql://root:secret@localhost:3306/demo",
        },
        headers=headers_a,
    )
    assert response.status_code == 201

    with session_factory() as db:
        actions = [item.action for item in db.query(AuditLogModel).order_by(AuditLogModel.created_at).all()]

    assert "USER_LOGIN" in actions
    assert "database_connection.create" in actions


def test_secret_values_are_never_returned_from_database_connection_api(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, _session_factory = enterprise_client
    org, _user_a, _user_b, workspace_a, _workspace_b, headers_a, _headers_b = _enterprise_fixture(client)
    raw_secret = "mysql://root:SuperSecret123!@localhost:3306/demo"
    create_response = client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": workspace_a["id"],
            "engine": "mysql",
            "name": "Secret DB",
            "connection_string": raw_secret,
        },
        headers=headers_a,
    )
    assert create_response.status_code == 201
    list_response = client.get(
        f"/databases/connections?organization_id={org['id']}&workspace_id={workspace_a['id']}",
        headers=headers_a,
    )

    assert raw_secret not in create_response.text
    assert "SuperSecret123" not in create_response.text
    assert raw_secret not in list_response.text
    assert "SuperSecret123" not in list_response.text
