from __future__ import annotations

import logging
from pathlib import Path

from legacydb_copilot.services.evidence_execution_service import execute_evidence_plan
from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.services.scan_policy_service import ScanPolicyService


class RecordingConnector:
    engine_type = "sql_server"

    def __init__(self) -> None:
        self.executed = False

    def estimate_table_rows(self, _table: str) -> int:
        return 10_000

    def execute_read_only_query(self, _sql: str, limit: int = 100) -> list[dict[str, object]]:
        self.executed = True
        return [{"allowed": True, "limit": limit}]


def test_demo_evaluation_policy_is_logged_as_allowed_before_execution(caplog) -> None:
    connector = RecordingConnector()
    policy = ScanPolicyService().resolve_policy(
        environment_type="evaluation",
        max_scan_rows=500,
        default_max_rows=100,
    )

    with caplog.at_level(logging.INFO):
        result = execute_evidence_plan(
            connector,
            [PlannedQuery("Inspect evaluation rows", "SELECT * FROM dbo.payroll", query_id="Q-1")],
            provider="sql_server",
            scan_policy=policy,
            workspace_id="workspace-evaluation",
            connection_id="connection-evaluation",
        )

    decision_log = next(
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("scan_policy_decision ")
    )
    execution_log_index = next(
        index
        for index, record in enumerate(caplog.records)
        if record.getMessage().startswith("evidence_plan executed ")
    )
    decision_log_index = next(
        index
        for index, record in enumerate(caplog.records)
        if record.getMessage().startswith("scan_policy_decision ")
    )

    assert connector.executed is True
    assert result[0].execution_status == "succeeded"
    assert "workspace_id=workspace-evaluation" in decision_log
    assert "connection_id=connection-evaluation" in decision_log
    assert "environment=evaluation" in decision_log
    assert "policy=evaluation_readonly" in decision_log
    assert "decision=allowed" in decision_log
    assert "reason=bounded_readonly_scan" in decision_log
    assert "component=ProductionReadSafetyValidator" in decision_log
    assert decision_log_index < execution_log_index


def test_evaluation_bootstrap_is_explicit_and_migration_does_not_infer_names() -> None:
    migration = Path(
        "alembic/versions/0011_demo_evaluation_connection_metadata.py"
    ).read_text(encoding="utf-8")
    bootstrap = Path("evaluation/local_environment.py").read_text(encoding="utf-8")

    assert '"demo_databases"' not in migration
    assert "Never infer it" in migration
    assert 'environment_type="evaluation"' in bootstrap


def test_local_sql_server_bootstrap_sets_evaluation_policy_and_read_only_metadata_access() -> None:
    configure = Path("scripts/evaluation/configure_local_sqlserver.py").read_text(
        encoding="utf-8"
    )
    provision = Path("scripts/evaluation/start-local-sqlserver.ps1").read_text(
        encoding="utf-8"
    )

    assert 'record.environment_type = "evaluation"' in configure
    assert "GRANT VIEW DEFINITION TO [evalreader]" in provision
    assert "DENY EXECUTE TO [evalreader]" in provision


def test_container_runs_migrations_before_starting_the_api() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "python -m alembic upgrade head && uvicorn" in dockerfile
