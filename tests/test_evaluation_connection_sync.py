from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.services import evaluation_connection_sync_service as service


class Database:
    def __init__(self):
        self.records = {}
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get(self, _model, connection_id):
        return self.records.setdefault(connection_id, SimpleNamespace())

    def commit(self):
        self.committed = True


def configure(monkeypatch):
    monkeypatch.setenv("EVALUATION_AZURE_CONNECTION_SYNC_ENABLED", "true")
    for domain, database in service.AZURE_EVALUATION_DATABASES.items():
        monkeypatch.setenv(f"EVAL_CONNECTION_ID_{domain}", f"id-{domain.casefold()}")
        monkeypatch.setenv(
            f"EVAL_APP_SQL_URL_{domain}",
            "mssql+pyodbc://legacydb_eval_reader:secret@"
            f"{service.AZURE_EVALUATION_SERVER}:1433/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server",
        )


def test_sync_persists_only_approved_identity_and_secret_references(monkeypatch):
    configure(monkeypatch)
    database = Database()
    monkeypatch.setattr(
        service,
        "create_session_factory",
        lambda _url: lambda: database,
    )

    count = service.sync_azure_evaluation_connections(
        Settings(environment=Environment.TESTING)
    )

    assert count == 5
    assert database.committed
    for record in database.records.values():
        assert record.host == service.AZURE_EVALUATION_SERVER
        assert record.port == 1433
        assert record.secret_ref.startswith("env://EVAL_APP_SQL_URL_")
        assert "secret" not in record.secret_ref


def test_sync_rejects_wrong_server_before_persistence(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv(
        "EVAL_APP_SQL_URL_PAYROLL",
        "mssql+pyodbc://legacydb_eval_reader:secret@evil.example.test:1433/"
        "EvalPayroll?driver=ODBC+Driver+18+for+SQL+Server",
    )

    with pytest.raises(RuntimeError, match="identity is invalid"):
        service.sync_azure_evaluation_connections(Settings(environment=Environment.TESTING))


def test_sync_constructs_urls_in_memory_from_managed_reader_password(monkeypatch):
    configure(monkeypatch)
    database = Database()
    monkeypatch.setenv("EVAL_READER_PASSWORD", "managed-secret")
    for domain in service.AZURE_EVALUATION_DATABASES:
        monkeypatch.setenv(f"EVAL_APP_SQL_URL_{domain}", "secret-placeholder")
    monkeypatch.setattr(
        service,
        "create_session_factory",
        lambda _url: lambda: database,
    )

    assert (
        service.sync_azure_evaluation_connections(
            Settings(environment=Environment.TESTING)
        )
        == 5
    )
    for domain, expected_database in service.AZURE_EVALUATION_DATABASES.items():
        url = service.make_url(os.environ[f"EVAL_APP_SQL_URL_{domain}"])
        assert url.host == service.AZURE_EVALUATION_SERVER
        assert url.database == expected_database
        assert url.username == service.AZURE_EVALUATION_READER
        assert url.password == "managed-secret"
        assert database.records[f"id-{domain.casefold()}"].secret_ref == (
            f"env://EVAL_APP_SQL_URL_{domain}"
        )


def test_sync_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EVALUATION_AZURE_CONNECTION_SYNC_ENABLED", raising=False)
    assert (
        service.sync_azure_evaluation_connections(Settings(environment=Environment.TESTING)) == 0
    )
