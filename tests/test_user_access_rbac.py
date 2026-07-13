from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.auth import Role
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import OrganizationModel, UserModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.security import hash_password


@pytest.fixture
def access_client(monkeypatch):
    monkeypatch.setenv("FEATURE_ENTERPRISE_RBAC_ENABLED", "true")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def db_override():
        with factory() as db:
            yield db
    app = create_fastapi_app()
    app.dependency_overrides[get_db_session] = db_override
    with factory() as db:
        org = OrganizationModel(name="Tenant", slug="tenant")
        other = OrganizationModel(name="Other", slug="other")
        db.add_all([org, other]); db.flush()
        admin = UserModel(organization_id=org.id, email="admin@test.io", password_hash=hash_password("StrongPass123!"), role=Role.ORG_ADMIN.value, full_name="Admin")
        regular = UserModel(organization_id=org.id, email="user@test.io", password_hash=hash_password("StrongPass123!"), role=Role.READ_ONLY.value, full_name="User")
        db.add_all([admin, regular]); db.commit()
        ids = {"org": org.id, "other": other.id, "admin": admin.id, "regular": regular.id}
    return TestClient(app), factory, ids


def login(client, email):
    body = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def payload(org, email="new@test.io", role="developer"):
    return {"organization_id": org, "email": email, "password": "SecurePass123!", "full_name": "New User", "role": role}


def test_admin_can_create_list_deactivate_and_reactivate_user(access_client):
    client, _factory, ids = access_client; headers = login(client, "admin@test.io")
    created = client.post("/admin/users", json=payload(ids["org"]), headers=headers); assert created.status_code == 201
    user_id = created.json()["id"]
    assert any(u["id"] == user_id for u in client.get(f"/admin/users?organization_id={ids['org']}", headers=headers).json())
    assert client.patch(f"/admin/users/{user_id}", json={"is_active": False}, headers=headers).json()["is_active"] is False
    assert client.patch(f"/admin/users/{user_id}", json={"is_active": True}, headers=headers).json()["is_active"] is True


def test_duplicate_email_and_weak_password_are_rejected(access_client):
    client, _factory, ids = access_client; headers = login(client, "admin@test.io")
    assert client.post("/admin/users", json=payload(ids["org"], "user@test.io"), headers=headers).status_code == 409
    weak = payload(ids["org"]); weak["password"] = "too-weak-123"
    assert client.post("/admin/users", json=weak, headers=headers).status_code == 422


def test_regular_user_cannot_manage_users(access_client):
    client, _factory, ids = access_client; headers = login(client, "user@test.io")
    assert client.get(f"/admin/users?organization_id={ids['org']}", headers=headers).status_code == 403
    assert client.post("/admin/users", json=payload(ids["org"]), headers=headers).status_code == 403


def test_org_admin_cannot_cross_tenants_or_assign_super_admin(access_client):
    client, _factory, ids = access_client; headers = login(client, "admin@test.io")
    assert client.post("/admin/users", json=payload(ids["other"]), headers=headers).status_code == 403
    assert client.post("/admin/users", json=payload(ids["org"], role="super_admin"), headers=headers).status_code in {403, 422}


def test_admin_cannot_change_own_role_or_disable_self(access_client):
    client, _factory, ids = access_client; headers = login(client, "admin@test.io")
    assert client.patch(f"/admin/users/{ids['admin']}", json={"role": "read_only_user"}, headers=headers).status_code == 403
    assert client.patch(f"/admin/users/{ids['admin']}", json={"is_active": False}, headers=headers).status_code == 403


def test_failed_creation_does_not_leave_partial_user(access_client):
    client, factory, ids = access_client; headers = login(client, "admin@test.io")
    client.post("/admin/users", json=payload(ids["org"], "user@test.io"), headers=headers)
    with factory() as db:
        assert db.query(UserModel).filter(UserModel.organization_id == ids["org"], UserModel.email == "user@test.io").count() == 1
