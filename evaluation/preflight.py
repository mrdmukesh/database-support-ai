from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib import parse, request

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from evaluation.framework.scenario_loader import load_scenarios
from evaluation.runners.mysql_database import MySQLDatabaseLifecycle
from evaluation.runners.public_api import EvaluationServiceTokenProvider
from evaluation.runners.sqlcmd_database import SqlCmdDatabaseLifecycle

DOMAINS = ("payroll", "clinic", "orders", "banking", "shipping")
DATABASES = (
    {domain: f"eval_{domain}" for domain in DOMAINS}
    if os.getenv("EVAL_DATABASE_ENGINE", "sql_server").lower() == "mysql"
    else dict(zip(DOMAINS, ("EvalPayroll", "EvalClinic", "EvalOrders", "EvalBanking", "EvalShipping"), strict=True))
)


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


@dataclass
class PreflightReport:
    checks: list[Check]

    @property
    def passed(self) -> bool:
        return all(item.status != "FAIL" for item in self.checks)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "checks": [asdict(item) for item in self.checks]}


def _csv(name: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}


def _http_json(method: str, url: str, token: str = "") -> object:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with request.urlopen(request.Request(url, headers=headers, method=method), timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _process_is_running(process_id: int) -> bool:
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, process_id)
        running = bool(handle)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
        return running
    os.kill(process_id, 0)
    return True


def _worker_health(
    pid_file: Path = Path(".tmp/local-evaluation/worker.pid"),
    *,
    require_runtime: bool = False,
) -> tuple[bool, str]:
    if os.getenv("EVALUATION_WORKER_ENABLED", "").casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True, "embedded evaluation worker is enabled in the API process"
    if not pid_file.is_file():
        return False, "worker pid file missing"
    try:
        worker_pid = int(pid_file.read_text(encoding="utf-8").strip())
        running = _process_is_running(worker_pid)
    except (OSError, ValueError):
        return False, "worker process is not running"
    if not running:
        return False, f"process {worker_pid} is not running"
    if require_runtime:
        runtime_file = pid_file.with_name("worker-runtime.json")
        try:
            runtime = json.loads(runtime_file.read_text(encoding="utf-8"))
            readiness = runtime.get("readiness", {})
            if readiness.get("status") != "ready":
                return False, "worker dependencies are not ready"
        except (OSError, ValueError, TypeError):
            return False, "worker runtime diagnostic is missing or invalid"
    return True, f"process {worker_pid} is running"


def run_preflight(*, check_live: bool = True) -> PreflightReport:
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str, *, warning: bool = False) -> None:
        checks.append(Check(name, "PASS" if ok else ("WARNING" if warning else "FAIL"), detail))

    database_url = os.getenv("EVAL_RESULTS_DATABASE_URL") or os.getenv("DATABASE_URL", "")
    if check_live and database_url:
        try:
            engine = create_engine(database_url)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                current = MigrationContext.configure(connection).get_current_revision()
            head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
            add("evaluation results database", True, "connectivity verified")
            add("Alembic migration head", current == head, f"database={current}; code={head}")
        except Exception as exc:
            add("evaluation results database", False, f"connection failed: {type(exc).__name__}")
            add("Alembic migration head", False, "not checked because database connectivity failed")
    else:
        add("evaluation results database", False, "DATABASE_URL is missing" if not database_url else "live checks disabled")
        add("Alembic migration head", False, "requires evaluation results database")

    application_url = os.getenv("DATABASE_URL", "")
    if check_live and application_url:
        try:
            with create_engine(application_url, pool_pre_ping=True).connect() as connection:
                connection.execute(text("SELECT 1"))
            add("application metadata database", True, "connectivity verified")
        except Exception as exc:
            add("application metadata database", False, f"connection failed: {type(exc).__name__}")
    else:
        add("application metadata database", False, "DATABASE_URL is missing")

    worker_ok, worker_detail = _worker_health(require_runtime=True)
    add("investigation worker health", worker_ok, worker_detail)

    base_url = os.getenv("EVAL_API_BASE_URL", "").rstrip("/")
    token = os.getenv("EVAL_ACCESS_TOKEN", "")
    service_auth = bool(os.getenv("EVAL_SERVICE_CLIENT_ID") and os.getenv("EVAL_SERVICE_CLIENT_SECRET"))
    auth_names = ["EVAL_ORGANIZATION_ID", "EVAL_WORKSPACE_ID", "EVAL_USER_ID"]
    missing_auth = [name for name in auth_names if not os.getenv(name)]
    if not token and not service_auth:
        missing_auth.append("EVAL_ACCESS_TOKEN or service credentials")
    add("authentication configuration", not missing_auth, "configured" if not missing_auth else "missing: " + ", ".join(missing_auth))
    if check_live and base_url:
        try:
            health = _http_json("GET", base_url + "/health")
            add("application API health", isinstance(health, dict) and health.get("status") in {"ok", "healthy"}, str(health.get("status")))
        except Exception as exc:
            add("application API health", False, f"unreachable: {type(exc).__name__}")
    else:
        add("application API health", False, "EVAL_API_BASE_URL is missing" if not base_url else "live checks disabled")

    connection_ids = {domain: os.getenv(f"EVAL_CONNECTION_ID_{domain.upper()}", "") for domain in DOMAINS}
    if check_live and base_url and (token or service_auth) and os.getenv("EVAL_ORGANIZATION_ID"):
        try:
            if service_auth:
                token = EvaluationServiceTokenProvider(base_url, os.environ["EVAL_SERVICE_CLIENT_ID"], os.environ["EVAL_SERVICE_CLIENT_SECRET"])()
            query = parse.urlencode({"organization_id": os.environ["EVAL_ORGANIZATION_ID"], "workspace_id": os.getenv("EVAL_WORKSPACE_ID", "")})
            rows = _http_json("GET", f"{base_url}/databases/connections?{query}", token)
            by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict)}
            for domain, connection_id in connection_ids.items():
                try:
                    row = by_id.get(connection_id)
                    expected = DATABASES[domain]
                    identity_ok = bool(
                        row
                        and row.get("database_name") == expected
                        and row.get("workspace_id") == os.getenv("EVAL_WORKSPACE_ID")
                    )
                    connectivity: object = {}
                    if identity_ok:
                        connectivity = _http_json(
                            "POST",
                            f"{base_url}/databases/connections/{connection_id}/test",
                            token,
                        )
                    connection_ok = bool(
                        isinstance(connectivity, dict) and connectivity.get("is_valid")
                    )
                    add(
                        f"{domain} application connection",
                        identity_ok and connection_ok,
                        (
                            f"expected database={expected}; "
                            f"identity={'valid' if identity_ok else 'invalid'}; "
                            f"connectivity={'verified' if connection_ok else 'failed'}"
                        ),
                    )
                except Exception as exc:
                    add(
                        f"{domain} application connection",
                        False,
                        f"connectivity check failed: {type(exc).__name__}",
                    )
        except Exception as exc:
            for domain in DOMAINS:
                add(f"{domain} application connection", False, f"connection inventory failed: {type(exc).__name__}")
    else:
        for domain, connection_id in connection_ids.items():
            add(f"{domain} application connection", False, "connection ID missing" if not connection_id else "live API authentication unavailable")
    add("application database access", os.getenv("EVAL_APPLICATION_DB_ACCESS_MODE", "").lower() == "read_only", "must be explicitly set to read_only")

    scenarios = []
    manifest_error = ""
    try:
        for domain in DOMAINS:
            scenarios.extend(load_scenarios(Path("evaluation_scenarios") / domain / "scenarios.json"))
    except Exception as exc:
        manifest_error = str(exc)
    add("125 scenario manifests", len(scenarios) == 125 and len({s.scenario_id for s in scenarios}) == 125, manifest_error or f"found {len(scenarios)} active/defined scenarios")
    missing_scripts = []
    for scenario in scenarios:
        for field in ("baseline_script", "setup_script", "verification_script", "cleanup_script"):
            if not Path(getattr(scenario, field)).is_file():
                missing_scripts.append(f"{scenario.scenario_id}:{field}")
    add("scenario scripts", not missing_scripts, "all baseline/setup/verification/cleanup scripts exist" if not missing_scripts else ", ".join(missing_scripts[:5]))

    judge_missing = [name for name in ("OPENAI_API_KEY", "EVAL_JUDGE_MODEL") if not os.getenv(name)]
    add("judge provider configuration", os.getenv("EVAL_JUDGE_PROVIDER", "openai") == "openai" and bool(os.getenv("OPENAI_API_KEY")), "OpenAI configured" if not judge_missing else "missing OPENAI_API_KEY")
    add("judge model configuration", bool(os.getenv("EVAL_JUDGE_MODEL")), os.getenv("EVAL_JUDGE_MODEL", "missing EVAL_JUDGE_MODEL"))
    costs = (os.getenv("EVAL_JUDGE_INPUT_COST_PER_MILLION"), os.getenv("EVAL_JUDGE_OUTPUT_COST_PER_MILLION"))
    try:
        cost_ok = all(value is not None and float(value) >= 0 for value in costs)
    except ValueError:
        cost_ok = False
    add("judge token cost configuration", cost_ok, "input and output rates configured" if cost_ok else "missing or invalid token rates")

    artifact_root = Path(os.getenv("EVAL_ARTIFACT_ROOT", "research/results"))
    try:
        artifact_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=artifact_root, delete=True):
            pass
        artifact_ok = True
    except OSError:
        artifact_ok = False
    add("writable artifact directory", artifact_ok, str(artifact_root.resolve()))

    mysql_mode = os.getenv("EVAL_DATABASE_ENGINE", "sql_server").lower() == "mysql"
    server = os.getenv("EVAL_MYSQL_HOST" if mysql_mode else "EVAL_SQL_SERVER", "")
    allowed_hosts = _csv("EVAL_ALLOWED_MYSQL_HOSTS" if mysql_mode else "EVAL_ALLOWED_SQL_HOSTS")
    allowed_databases = _csv("EVAL_ALLOWED_DATABASES")
    target = (
        server.casefold()
        if mysql_mode
        else (SqlCmdDatabaseLifecycle._target(server) if server else "")
    )
    approved_targets = (
        {item.casefold() for item in allowed_hosts}
        if mysql_mode
        else {SqlCmdDatabaseLifecycle._target(item) for item in allowed_hosts}
    )
    host = server.casefold() if mysql_mode else SqlCmdDatabaseLifecycle._host(server)
    safe_config = bool(
        target
        and target in approved_targets
        and not any(word in host for word in ("prod", "production"))
        and set(DATABASES.values()).issubset(allowed_databases)
    )
    add(
        "non-production SQL target allowlist",
        safe_config,
        f"target={target or 'missing'}; databases={','.join(sorted(allowed_databases)) or 'missing'}",
    )
    sql_auth = (
        ["EVAL_MYSQL_HOST", "EVAL_MYSQL_USER", "EVAL_MYSQL_PASSWORD"]
        if mysql_mode
        else ["EVAL_SQL_SERVER", "EVAL_SQL_ADMIN", "EVAL_SQL_PASSWORD"]
    )
    missing_sql = [name for name in sql_auth if not os.getenv(name)]
    if check_live and not missing_sql and safe_config:
        lifecycle = (
            MySQLDatabaseLifecycle(
                host=server,
                port=int(os.getenv("EVAL_MYSQL_PORT", "3306")),
                username=os.environ["EVAL_MYSQL_USER"],
                password=os.environ["EVAL_MYSQL_PASSWORD"],
                databases=DATABASES,
                allowed_hosts={item.lower() for item in allowed_hosts},
                allowed_databases=allowed_databases,
            )
            if mysql_mode
            else SqlCmdDatabaseLifecycle(server=server, username=os.environ["EVAL_SQL_ADMIN"], password=os.environ["EVAL_SQL_PASSWORD"], databases=DATABASES, allowed_hosts={item.lower() for item in allowed_hosts}, allowed_databases=allowed_databases)
        )
        for domain in DOMAINS:
            try:
                lifecycle.assert_safe_target(domain)
                add(f"{domain} evaluation marker", True, f"{DATABASES[domain]} marker verified")
            except Exception as exc:
                add(f"{domain} evaluation marker", False, str(exc))
    else:
        for domain in DOMAINS:
            add(f"{domain} evaluation marker", False, "missing SQL runner configuration" if missing_sql else "unsafe target or live checks disabled")

    production_source = Path("src/legacydb_copilot")
    forbidden = ("evaluation_scenarios", "expected_root_cause_concepts", "acceptable_fix_concepts")
    leaks = []
    for source in production_source.rglob("*.py"):
        content = source.read_text(encoding="utf-8", errors="ignore")
        if any(term in content for term in forbidden):
            leaks.append(str(source))
    add("application runtime ground-truth isolation", not leaks, "no evaluation expected-answer imports/references in production runtime" if not leaks else ", ".join(leaks))
    return PreflightReport(checks)


def print_report(report: PreflightReport) -> None:
    for check in report.checks:
        print(f"{check.status:7} {check.name}: {check.detail}")
    print(f"{'PASS' if report.passed else 'FAIL'}    overall preflight")
