from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from evaluation.framework.contracts import ScenarioContract
from evaluation.fixtures.validation import manifest_sql_consistency, validate_identifiers
from evaluation.runners.contracts import SetupFailedError, UnsafeSQLError


class SqlCmdDatabaseLifecycle:
    def __init__(self, *, server: str, username: str, password: str, databases: dict[str, str], allowed_hosts: set[str] | None = None, allowed_databases: set[str] | None = None, reader_username: str = "evalreader", reader_password: str | None = None):
        self.server = server
        self.username = username
        self.password = password
        self.databases = databases
        self.allowed_hosts = {self._host(item) for item in (allowed_hosts or {"localhost", "127.0.0.1"})}
        self.allowed_databases = allowed_databases or set(databases.values())
        self.reader_username = reader_username
        self.reader_password = reader_password or password

    def reset(self, scenario: ScenarioContract) -> None:
        self.assert_safe_target(scenario.domain)
        self._run(scenario.domain, Path(f"evaluation_databases/{scenario.domain}/sql/04_reset.sql"))

    def inject(self, scenario: ScenarioContract) -> None:
        self.assert_safe_target(scenario.domain)
        self._guard_script(scenario.setup_script)
        self._run(scenario.domain, Path(scenario.setup_script))

    def verify(self, scenario: ScenarioContract) -> dict[str, object]:
        consistency = manifest_sql_consistency(scenario)
        if not consistency["consistent"]:
            return {"verified": False, "fixture_status": "FIXTURE_MANIFEST_MISMATCH", "manifest_consistency": consistency}
        completed = self._run(
            scenario.domain, Path(scenario.verification_script), verification=True
        )
        entity = self._verify_entity(scenario, self.username, self.password)
        reader = self._verify_entity(scenario, self.reader_username, self.reader_password)
        linkage = self._verify_defect_linkage(scenario)
        verified = (
            entity["status"] == "ENTITY_FOUND"
            and reader["status"] == "ENTITY_FOUND"
            and linkage["valid"]
        )
        return {
            "stdout": completed.stdout,
            "verified": verified,
            "fixture_status": "VALID" if verified else "INVALID",
            "manifest_consistency": consistency,
            "entity": entity,
            "application_visibility": reader,
            "defect_linkage": linkage,
            "database": self.databases[scenario.domain],
        }

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

    def _run_query(self, domain: str, query: str, *, username: str | None = None, password: str | None = None):
        command = ["sqlcmd", "-S", self.server, "-U", username or self.username, "-P", password or self.password, "-C", "-b", "-h", "-1", "-W", "-d", self.databases[domain], "-Q", query]
        try:
            return subprocess.run(command, check=True, capture_output=True, text=True, env=dict(os.environ))
        except subprocess.CalledProcessError as exc:
            raise UnsafeSQLError(f"Evaluation target safety check failed: {exc.stderr or exc.stdout}") from exc

    def _verify_entity(self, scenario: ScenarioContract, username: str, password: str) -> dict[str, object]:
        try:
            validate_identifiers(scenario)
        except ValueError as exc:
            return {"status": "ENTITY_QUERY_FAILED", "reason": str(exc), "exact_row_count": 0}
        schema = scenario.expected_entity_schema
        table = scenario.expected_entity_table
        column = scenario.expected_entity_column
        value = scenario.expected_entity_value.replace("'", "''")
        qualified = f"[{schema}].[{table}]"
        query = (
            "SET NOCOUNT ON; "
            f"IF OBJECT_ID(N'{schema}.{table}',N'U') IS NULL SELECT N'ENTITY_TABLE_MISSING|0'; "
            f"ELSE IF COL_LENGTH(N'{schema}.{table}',N'{column}') IS NULL SELECT N'ENTITY_COLUMN_MISSING|0'; "
            "ELSE BEGIN DECLARE @expected NVARCHAR(4000)=N'" + value + "'; DECLARE @count INT; "
            f"SELECT @count=COUNT(*) FROM {qualified} WHERE [{column}]=@expected; "
            "SELECT CASE WHEN @count=0 THEN N'ENTITY_NOT_FOUND' WHEN @count=1 THEN N'ENTITY_FOUND' ELSE N'ENTITY_DUPLICATE' END+N'|'+CAST(@count AS NVARCHAR(20)); END"
        )
        try:
            output = self._run_query(scenario.domain, query, username=username, password=password).stdout.strip().splitlines()[-1]
            status, count = [item.strip() for item in output.split("|", 1)]
            return {
                "status": status,
                "schema": schema,
                "table": table,
                "column": column,
                "expected_value": scenario.expected_entity_value,
                "match_mode": scenario.expected_entity_match_mode,
                "exact_row_count": int(count),
                "duplicate": int(count) > 1,
                "visible_to_application_credentials": username == self.reader_username,
            }
        except Exception as exc:
            return {"status": "ENTITY_QUERY_FAILED", "reason": str(exc), "exact_row_count": 0}

    def _verify_defect_linkage(self, scenario: ScenarioContract) -> dict[str, object]:
        try:
            validate_identifiers(scenario)
            value = scenario.expected_entity_value.replace("'", "''")
            defect = scenario.expected_defect_value.replace("'", "''")
            query = (
                "SET NOCOUNT ON; DECLARE @entity NVARCHAR(4000)=N'" + value + "',@defect NVARCHAR(4000)=N'" + defect + "'; "
                f"SELECT COUNT(*) FROM [{scenario.expected_entity_schema}].[{scenario.expected_entity_table}] e "
                f"JOIN [{scenario.expected_entity_schema}].[{scenario.expected_defect_table}] d ON d.[{scenario.expected_defect_link_column}]=e.[{scenario.expected_entity_link_column}] "
                f"WHERE e.[{scenario.expected_entity_column}]=@entity AND d.[{scenario.expected_defect_column}]=@defect;"
            )
            output = self._run_query(scenario.domain, query).stdout.strip().splitlines()[-1].strip()
            count = int(output)
            return {"valid": count > 0, "linked_row_count": count, "defect_table": scenario.expected_defect_table, "defect_value": scenario.expected_defect_value}
        except Exception as exc:
            return {"valid": False, "linked_row_count": 0, "reason": str(exc)}

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
