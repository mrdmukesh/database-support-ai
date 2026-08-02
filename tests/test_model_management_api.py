from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.auth import Role
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import OrganizationModel, UserModel, WorkspaceModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.security import hash_password


@pytest.fixture
def model_client(monkeypatch):
    monkeypatch.setenv("MODEL_SELECTION_ENABLED", "true")
    monkeypatch.setenv("MODEL_SELECTION_AUTOMATIC_ENABLED", "true")
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def db_override():
        with factory() as db:
            yield db

    app = create_fastapi_app()
    app.dependency_overrides[get_db_session] = db_override
    with factory() as db:
        org = OrganizationModel(name="Models", slug="models")
        db.add(org)
        db.flush()
        workspace = WorkspaceModel(organization_id=org.id, name="Production", slug="production")
        admin = UserModel(
            organization_id=org.id,
            email="admin@models.test",
            password_hash=hash_password("StrongPass123!"),
            role=Role.ORG_ADMIN.value,
            full_name="Admin",
        )
        user = UserModel(
            organization_id=org.id,
            email="user@models.test",
            password_hash=hash_password("StrongPass123!"),
            role=Role.DEVELOPER.value,
            full_name="User",
        )
        db.add_all([workspace, admin, user])
        db.commit()
        ids = {"org": org.id, "workspace": workspace.id, "user": user.id}
    return TestClient(app), ids


def login(client: TestClient, email: str) -> dict[str, str]:
    token = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def catalog_payload(org: str) -> dict:
    return {
        "organization_id": org,
        "display_name": "Fast",
        "provider": "openai",
        "provider_model_id": "configured-fast",
        "model_category": "fast",
        "description": "Routine investigations",
        "enabled": True,
        "default_reasoning_effort": "low",
        "maximum_reasoning_effort": "medium",
        "cost_tier": "low",
        "latency_tier": "low",
        "recommended_usage": "Routine",
        "availability_status": "available",
        "sort_order": 10,
        "premium": False,
        "automatic_eligible": True,
    }


def test_admin_catalog_policy_and_user_available_flow(model_client):
    client, ids = model_client
    admin = login(client, "admin@models.test")
    created = client.post("/admin/models", json=catalog_payload(ids["org"]), headers=admin)
    assert created.status_code == 201
    model_id = created.json()["id"]
    policy = client.patch(
        f"/admin/model-policies/{ids['org']}",
        json={
            "user_selection_enabled": True,
            "automatic_mode_enabled": True,
            "global_default_model_id": model_id,
            "automatic_candidate_ids": [model_id],
            "allowed_environments": ["production"],
        },
        headers=admin,
    )
    assert policy.status_code == 200
    user = login(client, "user@models.test")
    available = client.get(
        f"/models/available?workspace_id={ids['workspace']}&environment=production",
        headers=user,
    )
    assert available.status_code == 200
    assert [item["display_name"] for item in available.json()["options"]] == ["Automatic", "Fast"]
    assert "provider_model_id" not in str(available.json())


def test_ordinary_user_cannot_manage_catalog_or_read_admin_audit(model_client):
    client, ids = model_client
    user = login(client, "user@models.test")
    assert (
        client.get(f"/admin/models?organization_id={ids['org']}", headers=user).status_code == 403
    )
    assert (
        client.get(
            f"/admin/model-selection-audit?organization_id={ids['org']}", headers=user
        ).status_code
        == 403
    )
