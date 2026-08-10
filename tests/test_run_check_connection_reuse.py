from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from legacydb_copilot.db.connector import ConnectionPool, DatabaseConnectionError
from legacydb_copilot.db.models import DatabaseConnectionModel, VerificationCheckModel
from legacydb_copilot.routers import chat
from legacydb_copilot.schemas import VerificationRunRequest


class FakeDatabase:
    def __init__(self, *, connection=None, check=None):
        self.connection = connection
        self.check = check
        self.requested_connection_ids = []
        self.committed = False

    def get(self, model, record_id):
        if model is DatabaseConnectionModel:
            self.requested_connection_ids.append(record_id)
            return self.connection
        if model is VerificationCheckModel:
            return self.check
        return None

    def commit(self):
        self.committed = True

    def refresh(self, _record):
        return None


class RecordingConnector:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1

    def execute_read_only_query(self, sql, limit=25, parameters=None):
        self.calls.append((sql, limit, parameters))
        return self.rows


def investigation(**overrides):
    values = {
        "id": "investigation-1",
        "organization_id": "organization-1",
        "workspace_id": "workspace-1",
        "connection_id": "connection-1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def connection(**overrides):
    values = {
        "id": "connection-1",
        "organization_id": "organization-1",
        "workspace_id": "workspace-1",
        "engine": "sql_server",
        "host": "sql.example.test",
        "port": 1433,
        "database_name": "ExampleDatabase",
        "secret_ref": "keyvault://example-connection",
        "is_active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_run_check_reuses_exact_investigation_connector_without_secret_resolution(
    monkeypatch,
) -> None:
    existing = RecordingConnector()
    pool = SimpleNamespace(
        get_existing=lambda connection_id, configuration_key: existing,
    )
    db = FakeDatabase(connection=connection())
    monkeypatch.setattr(chat, "get_connection_pool", lambda: pool)
    monkeypatch.setattr(
        chat,
        "_build_connection_string",
        lambda _connection: pytest.fail("cached Run Check must not resolve the secret again"),
    )

    resolved = chat._active_connector_for_investigation(db, investigation())

    assert resolved is existing
    assert db.requested_connection_ids == ["connection-1"]
    assert existing.connect_calls == 0


def test_run_check_securely_builds_connector_only_when_pool_has_no_existing_entry(
    monkeypatch,
) -> None:
    created = RecordingConnector()

    class Pool:
        def get_existing(self, connection_id, *, configuration_key):
            assert connection_id == "connection-1"
            return None

        def get_or_create(
            self,
            connection_id,
            engine,
            connection_string,
            *,
            configuration_key,
        ):
            assert connection_id == "connection-1"
            assert connection_string == "resolved-securely"
            assert configuration_key
            return created

    monkeypatch.setattr(chat, "get_connection_pool", Pool)
    monkeypatch.setattr(chat, "_build_connection_string", lambda _connection: "resolved-securely")

    resolved = chat._active_connector_for_investigation(
        FakeDatabase(connection=connection()),
        investigation(),
    )

    assert resolved is created
    assert created.connect_calls == 1


def test_run_check_rejects_connection_outside_investigation_workspace(monkeypatch) -> None:
    monkeypatch.setattr(
        chat,
        "get_connection_pool",
        lambda: pytest.fail("cross-workspace connection must not reach the pool"),
    )
    db = FakeDatabase(connection=connection(workspace_id="another-workspace"))

    with pytest.raises(HTTPException) as raised:
        chat._active_connector_for_investigation(db, investigation())

    assert raised.value.status_code == 404


def test_run_check_connection_failure_remains_controlled(monkeypatch) -> None:
    pool = SimpleNamespace(
        get_existing=lambda _connection_id, configuration_key: None,
        get_or_create=lambda *_args: pytest.fail("failed resolution must not create a connector"),
    )
    monkeypatch.setattr(chat, "get_connection_pool", lambda: pool)
    monkeypatch.setattr(
        chat,
        "_build_connection_string",
        lambda _connection: (_ for _ in ()).throw(DatabaseConnectionError("unavailable")),
    )

    with pytest.raises(HTTPException) as raised:
        chat._active_connector_for_investigation(
            FakeDatabase(connection=connection()),
            investigation(),
        )

    assert raised.value.status_code == 400
    assert "Verification connection failed" in raised.value.detail


def test_run_check_route_preserves_parameters_and_returns_result_rows(monkeypatch) -> None:
    sql = "SELECT AssetCode FROM ops.Asset WHERE AssetCode = :asset_code"
    connector = RecordingConnector([{"AssetCode": "AST-2"}])
    inv = investigation()
    check = SimpleNamespace(
        id="check-1",
        investigation_id=inv.id,
        organization_id=inv.organization_id,
        workspace_id=inv.workspace_id,
        claim="Exact asset exists",
        verification_sql=sql,
        expected_result="Rows returned",
        source="SQL-1",
        parameters={"asset_code": "AST-2"},
        status="Pending",
    )
    db = FakeDatabase(check=check)
    monkeypatch.setattr(chat, "_get_verification_investigation", lambda *_args: inv)
    monkeypatch.setattr(chat, "_active_connector_for_investigation", lambda *_args: connector)
    monkeypatch.setattr(chat, "record_audit_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(chat, "_regenerate_report_with_verification", lambda *_args: None)

    result = chat.run_verification_check(
        "check-1",
        VerificationRunRequest(verification_sql=sql),
        db,
        SimpleNamespace(id="user-1", email="reviewer@example.com", full_name="Reviewer"),
    )

    assert connector.calls == [(sql, 25, {"asset_code": "AST-2"})]
    assert result.actual_result == {
        "columns": ["AssetCode"],
        "rows": [{"AssetCode": "AST-2"}],
        "row_count": 1,
    }
    assert db.committed is True


def test_connection_pool_exposes_existing_connector_without_connection_material() -> None:
    pool = ConnectionPool()
    connector = pool.get_or_create(
        "connection-1",
        chat.DatabaseEngine.SQLITE,
        "sqlite:///:memory:",
        configuration_key="configuration-1",
    )

    assert pool.get_existing("connection-1", configuration_key="configuration-1") is connector
    assert pool.get_existing("missing", configuration_key="configuration-1") is None
