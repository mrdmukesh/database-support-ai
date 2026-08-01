from __future__ import annotations

from types import SimpleNamespace

from legacydb_copilot.routers import databases


class Database:
    @staticmethod
    def get(_model, _connection_id):
        return SimpleNamespace(workspace_id="workspace")


def test_connection_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr(databases, "require_resource_owner_workspace", lambda *_a, **_k: None)
    monkeypatch.setattr(
        databases,
        "_build_connection_string",
        lambda _connection: (_ for _ in ()).throw(
            RuntimeError("password=top-secret;server=private")
        ),
    )

    result = databases.test_database_connection(
        "connection",
        Database(),
        SimpleNamespace(id="user"),
    )

    assert result["is_valid"] is False
    assert result["message"] == "Connection failed: RuntimeError"
    assert "top-secret" not in str(result)
