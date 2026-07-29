from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from evaluation.agentic_benchmark.runner import (
    AgenticBenchmarkRunner,
    BenchmarkSafetyRisk,
    capture_from_execution,
)
from evaluation.demo_payroll_benchmark.loader import (
    DATABASE,
    load_focused_pack,
    validate_focused_pack,
)
from evaluation.runners.contracts import RunnerConfig, RunnerContext
from evaluation.runners.investigation_reader import InvestigationPersistenceReader
from evaluation.runners.public_api import (
    EvaluationServiceTokenProvider,
    PublicInvestigationAPI,
)
from evaluation.runners.runner import EvaluationRunner
from evaluation.runners.store import SQLAlchemyExecutionStore
from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import DatabaseConnectionModel
from legacydb_copilot.db.session import create_session_factory

EXPECTED_CONNECTION_ID = "f59e11b9-e230-46e5-9d00-5602ced0ba82"
EXPECTED_HOST = "sql-dsai-eval-56ab486d.database.windows.net"
EXPECTED_READER = "eval_demo_payroll_reader"


class ReaderOnlyNoMutationLifecycle:
    """P13 deliberately uses prevalidated immutable fixtures."""

    def reset(self, scenario) -> None:
        return None

    def inject(self, scenario) -> None:
        return None

    def verify(self, scenario) -> dict[str, object]:
        return {
            "verified": True,
            "fixture_status": "PREVALIDATED_READER_ONLY",
            "database": DATABASE,
            "mutation_performed": False,
        }

    def cleanup(self, scenario) -> None:
        return None


def _runner(timeout: float, poll_interval: float) -> EvaluationRunner:
    settings = Settings.from_env()
    connection_id = os.environ["EVAL_DEMO_PAYROLL_CONNECTION_ID"]
    if connection_id != EXPECTED_CONNECTION_ID:
        raise BenchmarkSafetyRisk("Unexpected focused connection ID")
    if os.environ["EVAL_DEMO_PAYROLL_READER"] != EXPECTED_READER:
        raise BenchmarkSafetyRisk("Unexpected focused reader")
    host = (
        os.environ["EVAL_DEMO_PAYROLL_SQL_SERVER"]
        .removeprefix("tcp:")
        .split(",", 1)[0]
        .casefold()
    )
    focused_hosts = {
        item.strip().casefold()
        for item in os.environ["EVAL_DEMO_PAYROLL_ALLOWED_SQL_HOSTS"].split(",")
        if item.strip()
    }
    if host != EXPECTED_HOST or host not in focused_hosts:
        raise BenchmarkSafetyRisk("Focused SQL host identity or allowlist mismatch")
    app_factory = create_session_factory(settings.database_url)
    with app_factory() as session:
        connection = session.get(DatabaseConnectionModel, connection_id)
        if (
            connection is None
            or not connection.is_active
            or connection.database_name != DATABASE
            or connection.host.casefold() != EXPECTED_HOST
            or connection.workspace_id != os.environ["EVAL_WORKSPACE_ID"]
        ):
            raise BenchmarkSafetyRisk("Registered focused connection identity mismatch")
    results_factory = create_session_factory(
        os.getenv("EVAL_RESULTS_DATABASE_URL", settings.database_url)
    )
    api_base = os.getenv("EVAL_API_BASE_URL", "http://127.0.0.1:8000")
    provider = EvaluationServiceTokenProvider(
        api_base,
        os.environ["EVAL_SERVICE_CLIENT_ID"],
        os.environ["EVAL_SERVICE_CLIENT_SECRET"],
    )
    config = RunnerConfig(
        api_base_url=api_base,
        access_token="",
        context=RunnerContext(
            organization_id=os.environ["EVAL_ORGANIZATION_ID"],
            workspace_id=os.environ["EVAL_WORKSPACE_ID"],
            user_id=os.environ["EVAL_USER_ID"],
            connection_ids={"payroll": connection_id},
        ),
        timeout_seconds=timeout,
        poll_interval_seconds=poll_interval,
        max_api_retries=0,
        concurrency=1,
        ai_enabled=os.getenv("AI_REASONING_ENABLED", "false").casefold()
        in {"1", "true", "yes", "on"},
        database_engine="sqlserver",
    )
    return EvaluationRunner(
        config=config,
        database=ReaderOnlyNoMutationLifecycle(),
        api=PublicInvestigationAPI(
            api_base, token_provider=provider, request_timeout=timeout
        ),
        store=SQLAlchemyExecutionStore(results_factory),
        result_reader=InvestigationPersistenceReader(app_factory),
    )


def execute() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default="evaluation/results/demo-payroll-focused-p13"
    )
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--poll-interval", type=float, default=2)
    args = parser.parse_args()
    manifest, truth, scenarios, payload = load_focused_pack()
    validate_focused_pack(payload, os.getenv("EVAL_DEMO_PAYROLL_CONNECTION_ID", ""))
    existing = _runner(args.timeout, args.poll_interval)
    run_id = existing.create_run(
        f"demo-payroll-p13-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    )

    def investigate(entry):
        execution = existing.run_scenario(run_id, scenarios[entry.scenario_id])
        capture = capture_from_execution(entry, execution)
        if any("fault.DeniedEvidence" in sql for sql in capture.sql):
            raise BenchmarkSafetyRisk("DeniedEvidence access detected")
        if any(
            token in sql.casefold()
            for sql in capture.sql
            for token in ("insert ", "update ", "delete ", "merge ", "drop ", "alter ")
        ):
            raise BenchmarkSafetyRisk("Mutation SQL detected")
        return capture

    summary = AgenticBenchmarkRunner(
        manifest=manifest,
        ground_truth=truth,
        execute=investigate,
        output_root=Path(args.output) / run_id,
        database_engine="sqlserver",
        require_full_manifest=False,
    ).run()
    print(json.dumps({"run_id": run_id, **summary}, indent=2, default=str))


if __name__ == "__main__":
    execute()
