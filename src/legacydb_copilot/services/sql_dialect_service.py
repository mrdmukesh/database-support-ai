from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SqlDialect(StrEnum):
    SQL_SERVER = "sql_server"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    ORACLE = "oracle"
    SQLITE = "sqlite"


_ALIASES = {
    "sql_server": SqlDialect.SQL_SERVER,
    "mssql": SqlDialect.SQL_SERVER,
    "azure_sql": SqlDialect.SQL_SERVER,
    "azure sql": SqlDialect.SQL_SERVER,
    "postgres": SqlDialect.POSTGRESQL,
    "postgresql": SqlDialect.POSTGRESQL,
    "mysql": SqlDialect.MYSQL,
    "oracle": SqlDialect.ORACLE,
    "sqlite": SqlDialect.SQLITE,
}


def resolve_sql_dialect(provider: Any) -> SqlDialect:
    value = getattr(provider, "value", provider)
    normalized = str(value or "").strip().lower().replace("-", "_")
    try:
        return _ALIASES[normalized]
    except KeyError as exc:
        raise ValueError(f"SQL dialect is missing or unsupported: {normalized or '[missing]'}") from exc


def apply_row_limit(select_sql: str, limit: int, dialect: SqlDialect) -> str:
    sql = select_sql.strip().rstrip(";")
    if not re.match(r"^\s*select\b", sql, re.I):
        return sql
    if _has_row_limit(sql):
        return sql
    if dialect == SqlDialect.SQL_SERVER:
        return re.sub(r"^\s*select\b", f"SELECT TOP ({limit})", sql, count=1, flags=re.I)
    if dialect == SqlDialect.ORACLE:
        return f"{sql} FETCH FIRST {limit} ROWS ONLY"
    return f"{sql} LIMIT {limit}"


def _has_row_limit(sql: str) -> bool:
    return bool(
        re.search(r"\blimit\s+\d+\b", sql, re.I)
        or re.match(
            r"^\s*select\s+top\s*(?:\(\s*\d+\s*\)|\d+)(?=\s|$)",
            sql,
            re.I,
        )
        or re.search(r"\bfetch\s+(?:first|next)\s+\d+\s+rows\s+only\b", sql, re.I)
    )


@dataclass(frozen=True)
class SqlDialectDiagnostic:
    provider: str
    invalid_token: str
    planner_step: str
    query_id: str


class SqlDialectValidationError(ValueError):
    def __init__(self, diagnostic: SqlDialectDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(
            "Invalid SQL dialect token "
            f"{diagnostic.invalid_token!r} for provider {diagnostic.provider} "
            f"(planner_step={diagnostic.planner_step}, query_id={diagnostic.query_id})"
        )


def validate_sql_dialect(
    sql: str,
    dialect: SqlDialect,
    *,
    planner_step: str,
    query_id: str,
) -> None:
    normalized = re.sub(r"'(?:''|[^'])*'", "''", sql)
    invalid_token = ""
    if dialect == SqlDialect.SQL_SERVER and re.search(r"\blimit\b", normalized, re.I):
        invalid_token = "LIMIT"
    elif dialect in {SqlDialect.POSTGRESQL, SqlDialect.MYSQL, SqlDialect.SQLITE} and re.match(
        r"^\s*select\s+top\s*(?:\(|\d)", normalized, re.I
    ):
        invalid_token = "TOP"
    if invalid_token:
        raise SqlDialectValidationError(
            SqlDialectDiagnostic(dialect.value, invalid_token, planner_step, query_id)
        )
