from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from evaluation.framework.contracts import ScenarioContract
from evaluation.runners.contracts import SetupFailedError, UnsafeSQLError


class SqlCmdDatabaseLifecycle:
    def __init__(self, *, server: str, username: str, password: str, databases: dict[str, str], allowed_hosts: set[str] | None = None, allowed_databases: set[str] | None = None):
        self.server = server
        self.username = username
        self.password = password
        self.databases = databases
        self.allowed_hosts = {self._host(item) for item in (allowed_hosts or {"localhost", "127.0.0.1"})}
        self.allowed_databases = allowed_databases or set(databases.values())

    def reset(self, scenario: ScenarioContract) -> None:
        self.assert_safe_target(scenario.domain)
        self._run(scenario.domain, Path(f"evaluation_databases/{scenario.domain}/sql/04_reset.sql"))

    def inject(self, scenario: ScenarioContract) -> None:
        self.assert_safe_target(scenario.domain)
        self._guard_script(scenario.setup_script)
        self._run(scenario.domain, Path(scenario.setup_script))

    def verify(self, scenario: ScenarioContract) -> dict[str, str]:
        completed = self._run(
            scenario.domain, Path(scenario.verification_script), verification=True
        )
        return {"stdout": completed.stdout, "verified": True}

    def cleanup(self, scenario: ScenarioContract) -> None:
        self.assert_safe_target(scenario.domain)
        self._guard_script(scenario.cleanup_script)
        self._run(scenario.domain, Path(scenario.cleanup_script))

    @staticmethod
    def _host(server: str) -> str:
        return server.removeprefix("tcp:").split(",", 1)[0].strip().lower()

    def assert_safe_target(self, domain: str) -> None:
        database = self.databases.get(domain, "")
        host = self._host(self.server)
        if database not in self.allowed_databases or not database.lower().startswith("eval"):
            raise UnsafeSQLError(f"Database {database!r} is not in the evaluation allowlist")
        if host not in self.allowed_hosts or re.search(r"(^|[-_.])(prod|production)([-_.]|$)", host):
            raise UnsafeSQLError(f"Host {host!r} is not an allowed evaluation host")
        escaped_domain = domain.replace("'", "''")
        escaped_database = database.replace("'", "''")
        query = (
            "SET NOCOUNT ON; "
            f"IF DB_NAME() <> N'{escaped_database}' THROW 51010, 'Unexpected database', 1; "
            "IF NOT EXISTS (SELECT 1 FROM eval.evaluation_marker "
            f"WHERE MarkerId=1 AND DomainName=N'{escaped_domain}' AND DatabaseName=DB_NAME() AND IsSynthetic=1) "
            "THROW 51011, 'Evaluation marker missing', 1; SELECT 'evaluation_target_safe';"
        )
        self._run_query(domain, query)

    def _run_query(self, domain: str, query: str):
        command = ["sqlcmd", "-S", self.server, "-U", self.username, "-P", self.password, "-C", "-b", "-d", self.databases[domain], "-Q", query]
        try:
            return subprocess.run(command, check=True, capture_output=True, text=True, env=dict(os.environ))
        except subprocess.CalledProcessError as exc:
            raise UnsafeSQLError(f"Evaluation target safety check failed: {exc.stderr or exc.stdout}") from exc

    def _guard_script(self, script: str) -> None:
        path = Path(script).resolve()
        allowed = (Path.cwd() / "evaluation_scenarios").resolve()
        if allowed not in path.parents:
            raise UnsafeSQLError("Scenario SQL path escaped evaluation_scenarios")

    def _run(self, domain: str, script: Path, *, verification: bool = False):
        command = [
            "sqlcmd",
            "-S",
            self.server,
            "-U",
            self.username,
            "-P",
            self.password,
            "-C",
            "-b",
            "-d",
            self.databases[domain],
            "-i",
            str(script.resolve()),
        ]
        env = dict(os.environ)
        try:
            return subprocess.run(
                command,
                cwd=script.resolve().parent,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            kind = SetupFailedError if verification else RuntimeError
            raise kind(f"sqlcmd script failed ({script.name}): {exc.stderr or exc.stdout}") from exc
