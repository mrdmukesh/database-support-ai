from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.auth import Role
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    InvestigationModel,
    LLMInvocationAuditModel,
    DatabaseConnectionModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.security import hash_password
from legacydb_copilot.services.llm_invocation_audit_service import InvocationContext
from legacydb_copilot.services.llm_provider_client import AuditedLLMProviderClient, ProviderRequest


@pytest.fixture
def audit_api():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_fastapi_app()

    def db_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = db_override
    with factory() as db:
        org = OrganizationModel(name="Audit Org", slug="audit-org")
        other = OrganizationModel(name="Other Org", slug="other-org")
        db.add_all([org, other]); db.flush()
        admin = UserModel(organization_id=org.id, email="admin@audit.test", password_hash=hash_password("StrongPass123!"), role=Role.ORG_ADMIN.value)
        regular = UserModel(organization_id=org.id, email="regular@audit.test", password_hash=hash_password("StrongPass123!"), role=Role.READ_ONLY.value)
        outsider = UserModel(organization_id=other.id, email="outside@audit.test", password_hash=hash_password("StrongPass123!"), role=Role.ORG_ADMIN.value)
        workspace = WorkspaceModel(organization_id=org.id, name="Audit", slug="audit")
        db.add_all([admin, regular, outsider, workspace]); db.flush()
        connection = DatabaseConnectionModel(
            organization_id=org.id, workspace_id=workspace.id, engine="sqlite",
            name="Clinical", database_name="clinical", secret_ref="env://TEST_DATABASE_URL",
        )
        db.add(connection); db.flush()
        investigation = InvestigationModel(
            id="INV-APT-2101", organization_id=org.id, workspace_id=workspace.id,
            created_by_id=admin.id, user_question="Investigate appointment APT-2101.",
            llm_audit_outcome="AI_SKIPPED_BY_EVIDENCE_GATE",
            llm_audit_reason="evidence_gate_not_reproduced",
        )
        db.add(investigation)
        db.add(LLMInvocationAuditModel(
            organization_id=org.id, workspace_id=workspace.id, investigation_id="INV-WITH-CALL",
            investigation_run_id="RUN-1", logical_request_id="logical-1", agent_name="reasoning_agent",
            stage_name="Root Cause Reasoning", provider="openai", model_name="gpt-test",
            request_payload_hash="a" * 64, started_at=datetime(2026, 7, 25, tzinfo=UTC),
            completed_at=datetime(2026, 7, 25, 0, 0, 1, tzinfo=UTC),
            duration_ms=1000, status="completed", user_prompt_sanitized="sanitized needle",
        ))
        db.commit()
        ids = {"org": org.id, "workspace": workspace.id, "admin": admin.id, "connection": connection.id}
    return TestClient(app), factory, ids


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_authorized_admin_has_read_only_access_and_regular_user_is_forbidden(audit_api) -> None:
    client, _factory, _ids = audit_api
    admin = login(client, "admin@audit.test")
    regular = login(client, "regular@audit.test")
    assert client.get("/admin/llm-invocations", headers=admin).status_code == 200
    assert client.get("/admin/llm-invocations", headers=regular).status_code == 403
    assert client.post("/admin/llm-invocations", headers=admin, json={}).status_code == 405
    assert client.put("/admin/llm-invocations/anything", headers=admin, json={}).status_code == 405
    assert client.delete("/admin/llm-invocations/anything", headers=admin).status_code == 405


def test_zero_invocation_investigation_returns_evidence_gate_reason(audit_api) -> None:
    client, _factory, _ids = audit_api
    response = client.get(
        "/admin/investigations/INV-APT-2101/llm-invocations",
        headers=login(client, "admin@audit.test"),
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["zero_invocation_explanation"] == {
        "code": "AI_SKIPPED_BY_EVIDENCE_GATE",
        "reason": "evidence_gate_not_reproduced",
    }


def test_tenant_isolation_and_combined_filters(audit_api) -> None:
    client, _factory, _ids = audit_api
    admin = login(client, "admin@audit.test")
    outsider = login(client, "outside@audit.test")
    query = (
        "/admin/llm-invocations?investigation_id=INV-WITH-CALL"
        "&stage_name=Root%20Cause%20Reasoning&model=gpt-test&status=completed"
        "&search=needle&started_after=2026-07-24T00:00:00Z"
        "&started_before=2026-07-26T00:00:00Z"
    )
    assert client.get(query, headers=admin).json()["total"] == 1
    assert client.get(query, headers=outsider).json()["total"] == 0


def test_server_pagination_sorting_and_page_size_validation(audit_api) -> None:
    client, factory, ids = audit_api
    with factory() as db:
        for index in range(30):
            db.add(LLMInvocationAuditModel(
                organization_id=ids["org"], workspace_id=ids["workspace"],
                investigation_id=f"INV-PAGE-{index:02d}", logical_request_id=f"logical-{index}",
                agent_name="reasoning_agent", stage_name="Root Cause Reasoning",
                provider="openai", model_name="gpt-test", request_payload_hash="b" * 64,
                started_at=datetime(2026, 7, 26, 0, index, tzinfo=UTC), status="completed",
                user_prompt_sanitized=f"sanitized prompt {index}",
            ))
        db.commit()
    headers = login(client, "admin@audit.test")
    response = client.get(
        "/admin/llm-invocations?page=2&page_size=10&sort_by=started_at&sort_direction=asc",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 10
    assert payload["total_items"] == payload["total"] == 31
    assert payload["total_pages"] == 4
    assert payload["has_previous"] is True
    assert payload["has_next"] is True
    assert len(payload["items"]) == 10
    assert payload["items"][0]["prompt_preview"].startswith("sanitized prompt")
    assert client.get("/admin/llm-invocations?page_size=101", headers=headers).status_code == 422
    assert client.get("/admin/llm-invocations?sort_by=drop_table", headers=headers).status_code == 422


def test_apt_2101_submission_audits_every_actual_provider_call(
    audit_api, monkeypatch
) -> None:
    client, _factory, ids = audit_api

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self):
            return (
                b'{"id":"provider-apt","output_text":"sanitized response",'
                b'"usage":{"input_tokens":11,"output_tokens":7,"total_tokens":18}}'
            )

    monkeypatch.setattr(
        "legacydb_copilot.services.llm_provider_client.request.urlopen",
        lambda *_args, **_kwargs: Response(),
    )

    from legacydb_copilot.routers import chat as chat_router

    def run_dynamic(db, payload, _generated_by):
        investigation_id = "INV-APT-2101-AUDITED"
        for agent, stage in [
            ("context_discovery_agent", "Metadata Discovery"),
            ("reasoning_agent", "Root Cause Reasoning"),
        ]:
            context = InvocationContext(
                organization_id=payload.organization_id,
                workspace_id=payload.workspace_id,
                user_id=payload.user_id,
                investigation_id=investigation_id,
                investigation_run_id=investigation_id,
                correlation_id=investigation_id,
                agent_name=agent,
                stage_name=stage,
                logical_request_id=f"{investigation_id}-{agent}",
            )
            AuditedLLMProviderClient(db=db, context=context).invoke_json(ProviderRequest(
                provider="openai", model="gpt-test", endpoint="https://provider/responses",
                api_key="never-persist-this-key",
                body={
                    "model": "gpt-test",
                    "input": [{"role": "user", "content": payload.question}],
                    "sample_rows": [{"patient": "Jane Doe", "diagnosis": "private"}],
                },
                system_prompt="Return evidence-backed JSON. password=hidden",
                user_prompt='{"sample_rows":[{"patient":"Jane Doe","diagnosis":"private"}]}',
                input_cost_per_million=2.0,
                output_cost_per_million=8.0,
            ))
        metadata = chat_router._empty_investigation_metadata()
        metadata.update({
            "investigation_id": investigation_id,
            "detected_intent": "PRODUCTION_INVESTIGATION",
            "answer_provenance": "AI_ANSWERED",
            "ai_debug_trace": {
                "ai_reasoning_invoked": True,
                "ai_outcome": "success",
                "input_tokens": 11,
                "output_tokens": 7,
            },
        })
        return "Investigation complete.", ["Clinical"], 0.9, None, metadata

    monkeypatch.setattr(chat_router, "_run_dynamic_investigation", run_dynamic)
    response = client.post(
        "/chat/ask",
        headers=login(client, "admin@audit.test"),
        json={
            "organization_id": ids["org"],
            "workspace_id": ids["workspace"],
            "connection_id": ids["connection"],
            "user_id": ids["admin"],
            "question": (
                "Investigate appointment APT-2101. Trace all related records across appointments, "
                "patients, doctors, laboratory requests, prescriptions, billing, and clinical workflow. "
                "Generate an evidence-backed investigation report."
            ),
        },
    )
    assert response.status_code == 201
    investigation_id = response.json()["investigation_id"]
    audit = client.get(
        f"/admin/llm-invocations?investigation_id={investigation_id}",
        headers=login(client, "admin@audit.test"),
    ).json()
    assert audit["total"] == 2
    assert {row["investigation_id"] for row in audit["items"]} == {investigation_id}
    assert {row["agent_name"] for row in audit["items"]} == {
        "context_discovery_agent", "reasoning_agent"
    }
    for row in audit["items"]:
        assert row["prompt_tokens"] == 11
        assert row["completion_tokens"] == 7
        assert row["total_tokens"] == 18
        assert row["duration_ms"] is not None
        assert row["estimated_cost"] is not None
        assert "never-persist-this-key" not in row["prompt_preview"]
        assert "Jane Doe" not in row["prompt_preview"]
        assert "private" not in row["prompt_preview"]
        detail = client.get(
            f"/admin/llm-invocations/{row['llm_invocation_id']}",
            headers=login(client, "admin@audit.test"),
        ).json()
        serialized = str(detail)
        assert "never-persist-this-key" not in serialized
        assert "Jane Doe" not in serialized
        assert "private" not in serialized
        assert "[REDACTED_" in serialized
