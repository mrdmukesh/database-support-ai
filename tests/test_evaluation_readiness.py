from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.cli.__main__ import execute
from evaluation.preflight import run_preflight
from evaluation.runners.contracts import UnsafeSQLError
from evaluation.runners.sqlcmd_database import SqlCmdDatabaseLifecycle


def test_preflight_reports_blocking_configuration_gaps(monkeypatch):
    for name in list(__import__("os").environ):
        if name.startswith("EVAL_") or name in {"DATABASE_URL", "OPENAI_API_KEY"}:
            monkeypatch.delenv(name, raising=False)
    report = run_preflight(check_live=False)
    assert not report.passed
    assert {item.status for item in report.checks} <= {"PASS", "FAIL", "WARNING"}
    assert any(item.name == "25 scenario manifests" and item.status == "PASS" for item in report.checks)


def test_sql_lifecycle_rejects_unlisted_database():
    lifecycle = SqlCmdDatabaseLifecycle(
        server="localhost,1433",
        username="eval_runner",
        password="secret",
        databases={"payroll": "PayrollProduction"},
        allowed_hosts={"localhost"},
        allowed_databases={"EvalPayroll"},
    )
    with pytest.raises(UnsafeSQLError):
        lifecycle.assert_safe_target("payroll")


def test_sql_lifecycle_requires_marker(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="evaluation_target_safe", stderr="")

    monkeypatch.setattr("evaluation.runners.sqlcmd_database.subprocess.run", fake_run)
    lifecycle = SqlCmdDatabaseLifecycle(
        server="eval-sql,1433",
        username="eval_runner",
        password="secret",
        databases={"payroll": "EvalPayroll"},
        allowed_hosts={"eval-sql"},
        allowed_databases={"EvalPayroll"},
    )
    lifecycle.assert_safe_target("payroll")
    query = calls[0][calls[0].index("-Q") + 1]
    assert "eval.evaluation_marker" in query
    assert "EvalPayroll" in query


def test_dry_run_does_not_require_live_configuration(capsys):
    execute(
        SimpleNamespace(
            command="run-scenario",
            scenario_id="shipping-pilot-001",
            dry_run=True,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["selected_database"] == "EvalShipping"
    assert payload["api_endpoint"].endswith("/chat/ask")


def test_generated_databases_contain_persistent_marker():
    for domain in ("payroll", "clinic", "orders", "banking", "shipping"):
        create = Path("evaluation_databases", domain, "sql", "01_create.sql").read_text()
        reset = Path("evaluation_databases", domain, "sql", "04_reset.sql").read_text()
        assert "CREATE TABLE eval.evaluation_marker" in create
        assert "evaluation_marker" not in reset
