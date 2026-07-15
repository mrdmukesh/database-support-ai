from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from evaluation.framework.scenario_loader import load_scenarios
from evaluation.judges.ai_judge import AIJudge, JudgeConfig
from evaluation.judges.openai_client import OpenAIJudgeClient
from evaluation.judges.store import AIJudgeService
from evaluation.runners.contracts import RunnerConfig, RunnerContext
from evaluation.runners.investigation_reader import InvestigationPersistenceReader
from evaluation.runners.public_api import EvaluationServiceTokenProvider, PublicInvestigationAPI
from evaluation.runners.runner import FAILED_STATUSES, EvaluationRunner
from evaluation.runners.sqlcmd_database import SqlCmdDatabaseLifecycle
from evaluation.runners.store import SQLAlchemyExecutionStore
from evaluation.preflight import DATABASES, DOMAINS, print_report, run_preflight
from evaluation.validators.store import DeterministicValidationService
from legacydb_copilot.config import Settings
from legacydb_copilot.db.session import create_session_factory

def all_scenarios():
    scenarios = []
    for domain in DOMAINS:
        scenarios.extend(load_scenarios(Path("evaluation_scenarios") / domain / "scenarios.json"))
    return [scenario for scenario in scenarios if scenario.active]


def build_store() -> SQLAlchemyExecutionStore:
    return SQLAlchemyExecutionStore(create_session_factory(Settings.from_env().database_url))


def build_judge_service(store: SQLAlchemyExecutionStore) -> AIJudgeService:
    settings = Settings.from_env()
    config = JudgeConfig(
        provider=os.getenv("EVAL_JUDGE_PROVIDER", "openai"),
        model=os.getenv("EVAL_JUDGE_MODEL", settings.llm_model),
        second_model=os.getenv("EVAL_SECOND_JUDGE_MODEL") or None,
        temperature=0.0,
        timeout_seconds=float(os.getenv("EVAL_JUDGE_TIMEOUT_SECONDS", "90")),
        max_retries=int(os.getenv("EVAL_JUDGE_MAX_RETRIES", "2")),
        retry_backoff_seconds=float(os.getenv("EVAL_JUDGE_RETRY_BACKOFF_SECONDS", "1")),
        random_pass_sample_rate=float(os.getenv("EVAL_HUMAN_REVIEW_SAMPLE_RATE", "0")),
        random_seed=os.getenv("EVAL_HUMAN_REVIEW_SAMPLE_SEED", "pilot-v1"),
    )
    api_key = required_env("OPENAI_API_KEY")
    client = OpenAIJudgeClient(
        api_key=api_key,
        base_url=settings.openai_base_url,
        input_cost_per_million=float(os.getenv("EVAL_JUDGE_INPUT_COST_PER_MILLION", "0")),
        output_cost_per_million=float(os.getenv("EVAL_JUDGE_OUTPUT_COST_PER_MILLION", "0")),
    )
    return AIJudgeService(store.session_factory, AIJudge(client, config), config)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Required environment variable is missing: {name}")
    return value


def pilot_configuration_fingerprint() -> str:
    values = {
        "api_base_url": os.getenv("EVAL_API_BASE_URL", ""),
        "workspace_id": os.getenv("EVAL_WORKSPACE_ID", ""),
        "sql_server": os.getenv("EVAL_SQL_SERVER", ""),
        "connections": {
            domain: os.getenv(f"EVAL_CONNECTION_ID_{domain.upper()}", "")
            for domain in DOMAINS
        },
        "databases": DATABASES,
    }
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()


def build_runner(args) -> EvaluationRunner:
    connection_ids = {
        domain: required_env(f"EVAL_CONNECTION_ID_{domain.upper()}") for domain in DOMAINS
    }
    api_base_url = os.getenv("EVAL_API_BASE_URL", "http://127.0.0.1:8000")
    service_client_id = os.getenv("EVAL_SERVICE_CLIENT_ID")
    service_client_secret = os.getenv("EVAL_SERVICE_CLIENT_SECRET")
    access_token = os.getenv("EVAL_ACCESS_TOKEN", "")
    if not access_token and not (service_client_id and service_client_secret):
        raise SystemExit("Configure EVAL_ACCESS_TOKEN or both EVAL_SERVICE_CLIENT_ID and EVAL_SERVICE_CLIENT_SECRET")
    token_provider = EvaluationServiceTokenProvider(api_base_url, service_client_id, service_client_secret) if service_client_id and service_client_secret else None
    config = RunnerConfig(
        api_base_url=api_base_url,
        access_token=access_token,
        context=RunnerContext(
            organization_id=required_env("EVAL_ORGANIZATION_ID"),
            workspace_id=required_env("EVAL_WORKSPACE_ID"),
            user_id=required_env("EVAL_USER_ID"),
            connection_ids=connection_ids,
        ),
        timeout_seconds=args.timeout,
        poll_interval_seconds=args.poll_interval,
        max_api_retries=args.api_retries,
        concurrency=args.concurrency,
    )
    database = SqlCmdDatabaseLifecycle(
        server=required_env("EVAL_SQL_SERVER"),
        username=required_env("EVAL_SQL_ADMIN"),
        password=required_env("EVAL_SQL_PASSWORD"),
        databases=DATABASES,
        allowed_hosts={item.strip().lower() for item in required_env("EVAL_ALLOWED_SQL_HOSTS").split(",") if item.strip()},
        allowed_databases={item.strip() for item in required_env("EVAL_ALLOWED_DATABASES").split(",") if item.strip()},
    )
    session_factory = create_session_factory(Settings.from_env().database_url)
    return EvaluationRunner(
        config=config,
        database=database,
        api=PublicInvestigationAPI(config.api_base_url, config.access_token, token_provider=token_provider),
        store=SQLAlchemyExecutionStore(session_factory),
        result_reader=InvestigationPersistenceReader(session_factory),
    )


def select_scenarios(args, scenarios):
    if args.command == "run-scenario":
        selected = [
            item for item in scenarios if item.scenario_id.lower() == args.scenario_id.lower()
        ]
    elif args.command == "run-domain":
        selected = [item for item in scenarios if item.domain == args.domain]
    elif args.command == "run-category":
        selected = [item for item in scenarios if item.category == args.category]
    elif args.command == "run-difficulty":
        selected = [item for item in scenarios if item.difficulty == args.difficulty]
    else:
        selected = scenarios
    if not selected:
        raise SystemExit("No active scenarios matched the selection")
    return selected


def latest_statuses(rows: list[dict]) -> dict[str, dict]:
    latest = {}
    for row in rows:
        if (
            row["scenario_id"] not in latest
            or row["attempt"] > latest[row["scenario_id"]]["attempt"]
        ):
            latest[row["scenario_id"]] = row
    return latest


def execute(args) -> None:
    if args.command == "preflight":
        report = run_preflight()
        print_report(report)
        if not report.passed:
            raise SystemExit(1)
        return
    scenarios = all_scenarios()
    if args.command == "run-scenario" and args.dry_run:
        selected = select_scenarios(args, scenarios)[0]
        print(json.dumps({
            "dry_run": True,
            "scenario_id": selected.scenario_id,
            "domain": selected.domain,
            "selected_database": DATABASES[selected.domain],
            "scenario_version": selected.scenario_version,
            "scripts": {"reset": f"evaluation_databases/{selected.domain}/sql/04_reset.sql", "setup": selected.setup_script, "verification": selected.verification_script, "cleanup": selected.cleanup_script},
            "api_endpoint": os.getenv("EVAL_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/") + "/chat/ask",
            "stages": ["database reset", "defect injection", "defect verification", "public investigation API", "bounded polling", "result persistence", "cleanup"],
            "judging_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("EVAL_JUDGE_MODEL")),
        }, indent=2))
        return
    store = build_store()
    if args.command in {"judge-run", "judge-result", "list-human-review"}:
        if args.command == "list-human-review":
            result = AIJudgeService(store.session_factory, None, None).list_human_review(
                args.run_id
            )
        else:
            service = build_judge_service(store)
            result = (
                service.judge_run(args.run_id)
                if args.command == "judge-run"
                else service.judge_result(args.result_id)
            )
        print(json.dumps(result, indent=2, default=str))
        return
    if args.command in {"validate-run", "validate-result", "show-failures"}:
        service = DeterministicValidationService(store.session_factory)
        if args.command == "validate-run":
            output = service.validate_run(args.run_id)
        elif args.command == "validate-result":
            output = service.validate_result(args.result_id)
        else:
            output = service.show_failures(args.run_id)
        print(json.dumps(output, indent=2, default=str))
        return
    if args.command == "status":
        print(json.dumps(store.statuses(args.run_id), indent=2))
        return
    if args.command in {"run-all", "pilot-smoke"}:
        report = run_preflight()
        print_report(report)
        if not report.passed:
            raise SystemExit("Pilot execution blocked: preflight failed")
    if args.command == "run-all":
        gate = Path(os.getenv("EVAL_ARTIFACT_ROOT", "research/results")) / ".pilot-smoke-passed.json"
        if not gate.is_file():
            raise SystemExit("Pilot execution blocked: a passing five-domain pilot-smoke is required")
        gate_data = json.loads(gate.read_text(encoding="utf-8"))
        if gate_data.get("configuration_fingerprint") != pilot_configuration_fingerprint():
            raise SystemExit("Pilot execution blocked: smoke gate belongs to different configuration")
        if not gate_data.get("passed") or gate_data.get("cleanup_failures") or gate_data.get("unexpected_connections"):
            raise SystemExit("Pilot execution blocked: smoke gate has cleanup or connection failures")
    runner = build_runner(args)
    if args.command == "pilot-smoke":
        selected = []
        for domain in DOMAINS:
            scenario_id = os.getenv(f"EVAL_SMOKE_SCENARIO_{domain.upper()}", f"{domain}-pilot-001")
            matches = [item for item in scenarios if item.scenario_id == scenario_id and item.domain == domain]
            if len(matches) != 1:
                raise SystemExit(f"Smoke scenario is invalid for {domain}: {scenario_id}")
            selected.append(matches[0])
        run_id = runner.create_run(args.run_name)
        results = [runner.run_scenario(run_id, scenario) for scenario in selected]
        statuses = {row["scenario_id"]: row for row in store.statuses(run_id)}
        validation_service = DeterministicValidationService(store.session_factory)
        judge_service = build_judge_service(store)
        rows = []
        for scenario, result in zip(selected, results, strict=True):
            status = statuses[scenario.scenario_id]
            deterministic = validation_service.validate_result(status["result_id"]) if result.status in {"completed", "partial_application_response"} else None
            judged = judge_service.judge_result(status["result_id"]) if deterministic else None
            rows.append({"scenario_id": scenario.scenario_id, "domain": scenario.domain, "setup_verification_result": result.extracted_result.get("setup_verification"), "selected_connection": result.raw_request.get("connection_id"), "investigation_id": result.investigation_id, "application_status": result.investigation_status, "deterministic_score": deterministic.get("final_score") if deterministic else None, "ai_judge_score": judged.get("primary", {}).get("weighted_score") if judged else None, "human_review": judged.get("human_review") if judged else None, "total_duration_seconds": result.timings.get("total_seconds"), "token_usage": result.usage_cost.get("token_usage"), "cost": (judged.get("primary", {}).get("estimated_cost_usd") if judged else result.usage_cost.get("estimated_cost")), "cleanup_status": result.extracted_result.get("cleanup_status")})
        unexpected = [row["scenario_id"] for row in rows if row["selected_connection"] != os.getenv(f"EVAL_CONNECTION_ID_{row['domain'].upper()}")]
        cleanup_failures = [row["scenario_id"] for row in rows if row["cleanup_status"] != "passed"]
        passed = all(result.status == "completed" for result in results) and not unexpected and not cleanup_failures and len(rows) == 5
        output = {"run_id": run_id, "run_name": args.run_name, "configuration_fingerprint": pilot_configuration_fingerprint(), "passed": passed, "cleanup_failures": cleanup_failures, "unexpected_connections": unexpected, "scenarios": rows}
        root = Path(os.getenv("EVAL_ARTIFACT_ROOT", "research/results")); root.mkdir(parents=True, exist_ok=True)
        (root / f"pilot-smoke-{run_id}.json").write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
        if passed:
            (root / ".pilot-smoke-passed.json").write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
        print(json.dumps(output, indent=2, default=str))
        if not passed:
            raise SystemExit(1)
        return
    if args.command in {"resume", "rerun-failed"}:
        run_id = args.run_id
        latest = latest_statuses(store.statuses(run_id))
        if args.command == "resume":
            selected = [
                scenario
                for scenario in scenarios
                if scenario.scenario_id not in latest
                or latest[scenario.scenario_id]["status"] in FAILED_STATUSES
            ]
        else:
            selected = [
                scenario
                for scenario in scenarios
                if scenario.scenario_id in latest
                and latest[scenario.scenario_id]["status"] in FAILED_STATUSES
            ]
    else:
        selected = select_scenarios(args, scenarios)
        run_id = runner.create_run(args.run_name)
    results = runner.run_many(run_id, selected)
    print(
        json.dumps(
            {"run_id": run_id, "results": [result.__dict__ for result in results]},
            indent=2,
            default=str,
        )
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="LegacyDB public-API evaluation runner")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--concurrency", type=int, default=1)
    common.add_argument("--timeout", type=float, default=float(os.getenv("EVAL_SCENARIO_TIMEOUT_SECONDS", "300")))
    common.add_argument("--poll-interval", type=float, default=float(os.getenv("EVAL_POLL_INTERVAL_SECONDS", "2")))
    common.add_argument("--api-retries", type=int, default=int(os.getenv("EVAL_API_MAX_RETRIES", "3")))
    common.add_argument("--run-name", default="pilot-v1")
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("run-scenario", parents=[common])
    command.add_argument("--scenario-id", required=True)
    command.add_argument("--dry-run", action="store_true")
    command = commands.add_parser("run-domain", parents=[common])
    command.add_argument("--domain", choices=DOMAINS, required=True)
    command = commands.add_parser("run-category", parents=[common])
    command.add_argument("--category", required=True)
    command = commands.add_parser("run-difficulty", parents=[common])
    command.add_argument("--difficulty", required=True)
    commands.add_parser("run-all", parents=[common])
    commands.add_parser("pilot-smoke", parents=[common])
    commands.add_parser("preflight")
    command = commands.add_parser("resume", parents=[common])
    command.add_argument("--run-id", required=True)
    command = commands.add_parser("rerun-failed", parents=[common])
    command.add_argument("--run-id", required=True)
    command = commands.add_parser("status")
    command.add_argument("--run-id", required=True)
    command = commands.add_parser("validate-run")
    command.add_argument("--run-id", required=True)
    command = commands.add_parser("validate-result")
    command.add_argument("--result-id", required=True)
    command = commands.add_parser("show-failures")
    command.add_argument("--run-id", required=True)
    command = commands.add_parser("judge-run")
    command.add_argument("--run-id", required=True)
    command = commands.add_parser("judge-result")
    command.add_argument("--result-id", required=True)
    command = commands.add_parser("list-human-review")
    command.add_argument("--run-id", required=True)
    return root


def main() -> None:
    execute(parser().parse_args())


if __name__ == "__main__":
    main()
