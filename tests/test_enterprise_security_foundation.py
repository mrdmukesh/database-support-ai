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
from legacydb_copilot.auth import Role
from legacydb_copilot.db.models import AuditLogModel, InvestigationModel, OrganizationModel, UserModel, WorkspaceMembershipModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.security import hash_password


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


def _seed_org(session_factory: sessionmaker, name: str, slug: str) -> dict:
    with session_factory() as db:
        org = OrganizationModel(name=name, slug=slug)
        db.add(org)
        db.commit()
        db.refresh(org)
        return {"id": org.id, "name": org.name, "slug": org.slug, "is_active": org.is_active}


def _seed_user(session_factory: sessionmaker, org_id: str, email: str, role: Role) -> dict:
    with session_factory() as db:
        user = UserModel(
            organization_id=org_id,
            email=email,
            full_name=email.split("@")[0],
            password_hash=hash_password("StrongPass123!"),
            role=role.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"id": user.id, "organization_id": user.organization_id, "email": user.email, "role": user.role}


def test_enterprise_organization_management_requires_super_admin(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = enterprise_client
    platform_org = _seed_org(session_factory, "Platform", "platform")
    tenant_org = _seed_org(session_factory, "Tenant", "tenant")
    _seed_user(session_factory, platform_org["id"], "root@example.com", Role.SUPER_ADMIN)
    _seed_user(session_factory, tenant_org["id"], "tenant-admin@example.com", Role.ORG_ADMIN)
    root_headers = _headers(client, "root@example.com")
    tenant_headers = _headers(client, "tenant-admin@example.com")

    unauthenticated = client.post("/organizations", json={"name": "Blocked", "slug": "blocked"})
    org_admin_create = client.post(
        "/organizations",
        json={"name": "Also Blocked", "slug": "also-blocked"},
        headers=tenant_headers,
    )
    super_admin_create = client.post(
        "/organizations",
        json={"name": "Created By Root", "slug": "created-by-root"},
        headers=root_headers,
    )
    super_admin_list = client.get("/organizations", headers=root_headers)
    org_admin_list = client.get("/organizations", headers=tenant_headers)

    assert unauthenticated.status_code == 401
    assert org_admin_create.status_code == 403
    assert super_admin_create.status_code == 201
    assert {item["slug"] for item in super_admin_list.json()} >= {"platform", "tenant", "created-by-root"}
    assert [item["slug"] for item in org_admin_list.json()] == ["tenant"]


def _enterprise_fixture(client: TestClient, session_factory: sessionmaker) -> tuple[dict, dict, dict, dict, dict, dict[str, str], dict[str, str]]:
    org = _seed_org(session_factory, "Enterprise Corp", "enterprise-corp")
    user_a = _create_user(client, org["id"], "owner-a@example.com")
    user_b = _create_user(client, org["id"], "owner-b@example.com")
    headers_a = _headers(client, "owner-a@example.com")
    headers_b = _headers(client, "owner-b@example.com")
    workspace_a = _workspace(client, org["id"], headers_a, "Workspace A")
    workspace_b = _workspace(client, org["id"], headers_b, "Workspace B")
    return org, user_a, user_b, workspace_a, workspace_b, headers_a, headers_b


def test_org_admin_can_see_all_org_workspaces_without_membership(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = enterprise_client
    org, _user_a, _user_b, workspace_a, workspace_b, headers_a, _headers_b = _enterprise_fixture(client, session_factory)

    response = client.get(f"/workspaces?organization_id={org['id']}", headers=headers_a)

    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {workspace_a["id"], workspace_b["id"]}


def test_workspace_roles_control_database_actions(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = enterprise_client
    org, dba_assigner, _user_b, workspace_a, _workspace_b, headers_owner, _headers_b = _enterprise_fixture(client, session_factory)
    dba = _seed_user(session_factory, org["id"], "workspace-dba@example.com", Role.READ_ONLY)
    viewer = _seed_user(session_factory, org["id"], "workspace-viewer@example.com", Role.READ_ONLY)
    dba_headers = _headers(client, "workspace-dba@example.com")
    viewer_headers = _headers(client, "workspace-viewer@example.com")

    assign_dba = client.put(
        f"/workspaces/{workspace_a['id']}/members/{dba['id']}",
        json={"user_id": dba["id"], "role": "DBA"},
        headers=headers_owner,
    )
    assign_viewer = client.put(
        f"/workspaces/{workspace_a['id']}/members/{viewer['id']}",
        json={"user_id": viewer["id"], "role": "VIEWER"},
        headers=headers_owner,
    )
    dba_create = client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": workspace_a["id"],
            "engine": "mysql",
            "name": "Workspace DBA DB",
            "connection_string": "mysql://root:secret@localhost:3306/demo",
        },
        headers=dba_headers,
    )
    viewer_create = client.post(
        "/databases/connections",
        json={
            "organization_id": org["id"],
            "workspace_id": workspace_a["id"],
            "engine": "mysql",
            "name": "Viewer DB",
            "connection_string": "mysql://root:secret@localhost:3306/demo",
        },
        headers=viewer_headers,
    )

    assert dba_assigner["id"]
    assert assign_dba.status_code == 200
    assert assign_viewer.status_code == 200
    assert dba_create.status_code == 201
    assert viewer_create.status_code == 403


def test_workspace_membership_cannot_cross_organization(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = enterprise_client
    _org, _user_a, _user_b, workspace_a, _workspace_b, headers_a, _headers_b = _enterprise_fixture(client, session_factory)
    other_org = _seed_org(session_factory, "Other Org", "other-org")
    outsider = _seed_user(session_factory, other_org["id"], "outsider@example.com", Role.READ_ONLY)

    response = client.put(
        f"/workspaces/{workspace_a['id']}/members/{outsider['id']}",
        json={"user_id": outsider["id"], "role": "DEVELOPER"},
        headers=headers_a,
    )

    assert response.status_code == 404


def test_user_cannot_access_another_workspace_report(
    enterprise_client: tuple[TestClient, sessionmaker],
    tmp_path: Path,
    monkeypatch,
) -> None:
    from legacydb_copilot.routers import reports as reports_router

    client, session_factory = enterprise_client
    org, _user_a, user_b, _workspace_a, workspace_b, headers_a, _headers_b = _enterprise_fixture(client, session_factory)
    scoped_a = _seed_user(session_factory, org["id"], "scoped-a@example.com", Role.READ_ONLY)
    scoped_headers_a = _headers(client, "scoped-a@example.com")
    investigation_id = "INV-SECURITY-001"
    with session_factory() as db:
        db.add(
            WorkspaceMembershipModel(
                organization_id=org["id"],
                workspace_id=_workspace_a["id"],
                user_id=scoped_a["id"],
                role="VIEWER",
                is_active=True,
            )
        )
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
    response = client.get(f"/reports/{investigation_id}/investigation_report.pdf", headers=scoped_headers_a)

    assert response.status_code == 403


def test_user_cannot_access_another_workspace_database(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = enterprise_client
    org, _user_a, _user_b, _workspace_a, workspace_b, headers_a, headers_b = _enterprise_fixture(client, session_factory)
    scoped_a = _seed_user(session_factory, org["id"], "db-scoped-a@example.com", Role.READ_ONLY)
    scoped_headers_a = _headers(client, "db-scoped-a@example.com")
    with session_factory() as db:
        db.add(
            WorkspaceMembershipModel(
                organization_id=org["id"],
                workspace_id=_workspace_a["id"],
                user_id=scoped_a["id"],
                role="VIEWER",
                is_active=True,
            )
        )
        db.commit()
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

    response = client.get(f"/databases/connections/{connection['id']}/schema", headers=scoped_headers_a)

    assert response.status_code == 403


def test_audit_events_are_written_for_login_and_connection_create(
    enterprise_client: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = enterprise_client
    org, _user_a, _user_b, workspace_a, _workspace_b, headers_a, _headers_b = _enterprise_fixture(client, session_factory)
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
    client, session_factory = enterprise_client
    org, _user_a, _user_b, workspace_a, _workspace_b, headers_a, _headers_b = _enterprise_fixture(client, session_factory)
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
