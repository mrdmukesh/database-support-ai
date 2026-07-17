from __future__ import annotations

import re
from pathlib import Path
import pymysql

from evaluation.framework.contracts import ScenarioContract
from evaluation.runners.contracts import SetupFailedError, UnsafeSQLError


def _split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(sql):
        char = sql[index]
        current.append(char)
        if char == "'":
            if quoted and index + 1 < len(sql) and sql[index + 1] == "'":
                current.append(sql[index + 1])
                index += 1
            else:
                quoted = not quoted
        elif char == ";" and not quoted:
            statement = "".join(current[:-1]).strip()
            if statement:
                statements.append(statement)
            current = []
        index += 1
    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder)
    return statements


def translate_tsql_batch(sql: str) -> list[str]:
    """Translate the bounded T-SQL subset used by evaluation fixtures to MySQL 8."""
    batches = re.split(r"(?im)^\s*GO\s*$", sql)
    translated: list[str] = []
    for batch in batches:
        batch = batch.strip()
        if not batch or re.match(r"(?is)^CREATE\s+(?:OR\s+ALTER\s+)?(?:PROCEDURE|FUNCTION|TRIGGER)\b", batch):
            continue
        batch = re.sub(r"(?im)^\s*SET\s+XACT_ABORT\s+ON\s*;?", "", batch)
        batch = re.sub(r"(?im)^\s*(?:BEGIN\s+TRANSACTION|COMMIT)\s*;?", "", batch)
        batch = re.sub(r"(?im)^\s*CREATE\s+SCHEMA\s+eval\s+AUTHORIZATION\s+dbo\s*;?", "", batch)
        batch = re.sub(
            r"(?im)^\s*DBCC\s+CHECKIDENT\s*\(\s*'(?:(?:eval|dbo)\.)?([^']+)'\s*,\s*RESEED\s*,\s*0\s*\)\s*;?",
            lambda match: f"ALTER TABLE `{match.group(1)}` AUTO_INCREMENT = 1;",
            batch,
        )
        batch = re.sub(r"(?im)^\s*SET\s+NOCOUNT\s+ON\s*;?", "", batch)
        batch = re.sub(r"(?im)^\s*:r\s+\S+\s*$", "", batch)
        batch = batch.replace("[", "`").replace("]", "`")
        batch = re.sub(r"\beval\.", "", batch, flags=re.I)
        batch = re.sub(r"\bdbo\.", "", batch, flags=re.I)
        batch = re.sub(r"\bN'", "'", batch)
        batch = re.sub(r"\bSYSNAME\b", "VARCHAR(128)", batch, flags=re.I)
        batch = re.sub(r"\bNVARCHAR\((\d+)\)", r"VARCHAR(\1)", batch, flags=re.I)
        batch = re.sub(r"\bNVARCHAR\(MAX\)", "LONGTEXT", batch, flags=re.I)
        batch = re.sub(r"\bDATETIME2\(3\)", "DATETIME(3)", batch, flags=re.I)
        batch = re.sub(r"\bBIT\b", "BOOLEAN", batch, flags=re.I)
        batch = re.sub(r"\bBIGINT\s+IDENTITY\(1,1\)", "BIGINT AUTO_INCREMENT", batch, flags=re.I)
        batch = re.sub(r"\bSYSUTCDATETIME\(\)", "UTC_TIMESTAMP(3)", batch, flags=re.I)
        batch = re.sub(
            r"\bDEFAULT\s+UTC_TIMESTAMP\(3\)",
            "DEFAULT CURRENT_TIMESTAMP(3)",
            batch,
            flags=re.I,
        )
        batch = re.sub(r"\bDB_NAME\(\)", "DATABASE()", batch, flags=re.I)
        batch = re.sub(
            r"DATEADD\(\s*(minute|hour|day)\s*,\s*(-?\d+)\s*,\s*UTC_TIMESTAMP\(3\)\s*\)",
            lambda m: (
                f"DATE_ADD(UTC_TIMESTAMP(3), INTERVAL {m.group(2)} {m.group(1).upper()})"
            ),
            batch,
            flags=re.I,
        )
        batch = re.sub(r"(?i)\bINSERT\s+(?!INTO\b)([A-Za-z_`])", r"INSERT INTO \1", batch)
        batch = batch.strip()
        if not batch:
            continue
        translated.extend(_split_statements(batch))
    return translated


class MySQLDatabaseLifecycle:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        databases: dict[str, str],
        allowed_hosts: set[str] | None = None,
        allowed_databases: set[str] | None = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.databases = databases
        self.allowed_hosts = {item.lower() for item in (allowed_hosts or {"localhost", "127.0.0.1"})}
        self.allowed_databases = allowed_databases or set(databases.values())

    def _connect(self, domain: str):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            database=self.databases[domain],
            autocommit=True,
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=60,
            write_timeout=60,
        )

    def assert_safe_target(self, domain: str) -> None:
        database = self.databases.get(domain, "")
        if self.host.lower() not in self.allowed_hosts or database not in self.allowed_databases:
            raise UnsafeSQLError("MySQL evaluation target is not in the local allowlist")
        if not database.lower().startswith("eval_"):
            raise UnsafeSQLError(f"Unsafe local evaluation database: {database}")
        with self._connect(domain) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM evaluation_marker "
                "WHERE MarkerId=1 AND DomainName=%s AND DatabaseName=DATABASE() AND IsSynthetic=1",
                (domain,),
            )
            if cursor.fetchone()[0] != 1:
                raise UnsafeSQLError("Local MySQL evaluation marker is missing")

    def reset(self, scenario: ScenarioContract) -> None:
        self.assert_safe_target(scenario.domain)
        self._run_file(scenario.domain, Path(f"evaluation_databases/{scenario.domain}/sql/04_reset.sql"))

    def inject(self, scenario: ScenarioContract) -> None:
        self.assert_safe_target(scenario.domain)
        self._guard_script(scenario.setup_script)
        self._run_file(scenario.domain, Path(scenario.setup_script))

    def verify(self, scenario: ScenarioContract) -> dict[str, object]:
        self.assert_safe_target(scenario.domain)
        sql = Path(scenario.verification_script).read_text(encoding="utf-8")
        condition = re.search(r"(?is)IF\s+NOT\s*\((.+)\)\s+THROW\s+\d+\s*,\s*'[^']*'\s*,\s*\d+\s*;", sql)
        simple_condition = re.search(r"(?is)IF\s+NOT\s+(EXISTS\s*\(.+?\))\s+THROW\s+\d+\s*,\s*'[^']*'\s*,\s*\d+\s*;", sql)
        selects = re.findall(r"(?is)(SELECT\s+'[^;]+;)", sql)
        if not condition and simple_condition:
            condition = simple_condition
        if not condition:
            raise SetupFailedError("MySQL verification translator could not find the scenario condition")
        expression = translate_tsql_batch("SELECT " + condition.group(1) + " AS verified;")[0]
        with self._connect(scenario.domain) as connection, connection.cursor() as cursor:
            cursor.execute(expression)
            verified = bool(cursor.fetchone()[0])
            if not verified:
                raise SetupFailedError("Scenario defect not reproducible")
            stdout = "verified=1"
            if selects:
                statement = translate_tsql_batch(selects[-1])[0]
                cursor.execute(statement)
                stdout = "\t".join(str(value) for value in cursor.fetchone())
        return {"stdout": stdout, "verified": True}

    def cleanup(self, scenario: ScenarioContract) -> None:
        self.assert_safe_target(scenario.domain)
        self._guard_script(scenario.cleanup_script)
        self._run_file(scenario.domain, Path(scenario.cleanup_script))

    def _guard_script(self, script: str) -> None:
        path = Path(script).resolve()
        allowed = (Path.cwd() / "evaluation_scenarios").resolve()
        if allowed not in path.parents:
            raise UnsafeSQLError("Scenario SQL path escaped evaluation_scenarios")

    def _run_file(self, domain: str, path: Path) -> None:
        sql = path.read_text(encoding="utf-8")
        includes = re.findall(r"(?im)^\s*:r\s+(\S+)\s*$", sql)
        statements = translate_tsql_batch(sql)
        try:
            with self._connect(domain) as connection, connection.cursor() as cursor:
                for statement in statements:
                    if re.match(r"(?is)^IF\s+", statement):
                        continue
                    cursor.execute(statement)
            for include in includes:
                self._run_file(domain, path.parent / include)
        except Exception as exc:
            raise RuntimeError(f"MySQL script failed ({path.name}): {exc}") from exc
