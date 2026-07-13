from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.dependencies import get_current_user


def _client() -> TestClient:
    app = create_fastapi_app()
    app.dependency_overrides[get_current_user] = lambda: type("HelpUser", (), {"id": "USER-1", "role": "read_only_user", "organization_id": "ORG-1"})()
    return TestClient(app)


def test_help_feedback_workflow_returns_steps() -> None:
    client = _client()

    response = client.post("/help/ask", json={"question": "How to provide feedback?"})

    assert response.status_code == 200
    body = response.json()
    assert "Feedback" in body["related_pages"]
    assert any("actual root cause" in step.lower() for step in body["steps"])


def test_help_verification_checks_returns_verification_steps() -> None:
    client = _client()

    response = client.post("/help/ask", json={"question": "How to run verification checks?"})

    assert response.status_code == 200
    body = response.json()
    assert "Verification Checks" in body["related_pages"]
    assert any("Run this check" in step or "Run all safe checks" in step for step in body["steps"])
    assert any("read-only" in warning.lower() for warning in body["warnings"])


def test_help_redirects_investigation_questions_to_ai_chat() -> None:
    client = _client()

    response = client.post("/help/ask", json={"question": "Why did APT-2005 duplicate?"})

    assert response.status_code == 200
    body = response.json()
    assert "AI Chat" in body["related_pages"]
    assert "database investigation" in body["answer"].lower()
    assert any("does not run sql" in warning.lower() for warning in body["warnings"])


def test_help_assistant_does_not_require_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_REASONING_ENABLED", "true")
    client = _client()

    response = client.post("/help/ask", json={"question": "How do I download reports?"})

    assert response.status_code == 200
    assert "Reports" in response.json()["related_pages"]


def test_help_assistant_never_accesses_database_connectors(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Help Assistant must not access customer database connections")

    monkeypatch.setattr("legacydb_copilot.db.connector.get_connection_pool", fail_if_called)
    client = _client()

    response = client.post("/help/ask", json={"question": "How do I connect a database?"})

    assert response.status_code == 200
    assert "Database Connection" in response.json()["related_pages"]


def test_help_assistant_requires_authentication() -> None:
    response = TestClient(create_fastapi_app()).post("/help/ask", json={"question": "How do I create a workspace?"})
    assert response.status_code == 401


def test_help_assistant_enforces_input_limit() -> None:
    response = _client().post("/help/ask", json={"question": "x" * 1001})
    assert response.status_code == 422
