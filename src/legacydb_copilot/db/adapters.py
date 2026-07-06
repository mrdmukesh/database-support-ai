from __future__ import annotations

from abc import ABC
import re
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from legacydb_copilot.common import DomainError
from legacydb_copilot.databases import DatabaseEngine


class BaseDatabaseAdapter(ABC):
    engine_type: DatabaseEngine

    def __init__(self, engine: Engine):
        self.engine = engine

    def list_tables(self) -> list[str]:
        return inspect(self.engine).get_table_names(schema=None)

    def list_views(self) -> list[str]:
        return inspect(self.engine).get_view_names(schema=None)

    def list_columns(self, table_name: str) -> list[dict[str, Any]]:
        return inspect(self.engine).get_columns(table_name)

    def list_indexes(self, table_name: str) -> list[dict[str, Any]]:
        return inspect(self.engine).get_indexes(table_name)

    def list_foreign_keys(self, table_name: str) -> list[dict[str, Any]]:
        return inspect(self.engine).get_foreign_keys(table_name)

    def get_primary_key(self, table_name: str) -> dict[str, Any]:
        return inspect(self.engine).get_pk_constraint(table_name)

    def list_procedures(self) -> list[str]:
        return []

    def get_procedure_definition(self, procedure_name: str) -> str:
        return ""

    def get_version(self) -> str:
        return "unknown"

    def estimate_table_rows(self, table_name: str) -> int | None:
        return None

    def explain_query(self, sql: str) -> list[dict[str, Any]]:
        explain_sql = sql if sql.strip().lower().startswith("explain") else f"EXPLAIN {sql}"
        with self.engine.connect() as conn:
            result = conn.execute(text(explain_sql))
            return [dict(row._mapping) for row in result.fetchall()]

    def execute_read_only_query(self, sql: str, limit: int = 1000) -> list[dict[str, Any]]:
        sql = self.apply_limit(sql, limit)
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row._mapping) for row in result.fetchall()]

    def apply_limit(self, sql: str, limit: int) -> str:
        stripped = sql.strip().rstrip(";")
        lowered = stripped.lower()
        if not lowered.startswith("select") or _has_limit_clause(lowered):
            return stripped
        return f"{stripped} LIMIT {limit}"


class MySQLAdapter(BaseDatabaseAdapter):
    engine_type = DatabaseEngine.MYSQL

    def list_procedures(self) -> list[str]:
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES "
                    "WHERE ROUTINE_TYPE='PROCEDURE' AND ROUTINE_SCHEMA=DATABASE()"
                )
            )
            return [row[0] for row in result.fetchall()]

    def get_procedure_definition(self, procedure_name: str) -> str:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT ROUTINE_DEFINITION FROM INFORMATION_SCHEMA.ROUTINES "
                    "WHERE ROUTINE_TYPE='PROCEDURE' AND ROUTINE_SCHEMA=DATABASE() AND ROUTINE_NAME=:name"
                ),
                {"name": procedure_name},
            ).first()
            return row[0] if row and row[0] else ""

    def get_version(self) -> str:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT VERSION()")).scalar() or "unknown"

    def estimate_table_rows(self, table_name: str) -> int | None:
        with self.engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT TABLE_ROWS FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:name"
                ),
                {"name": table_name.strip("`[]\"").split(".")[-1]},
            ).scalar()
            return int(value) if value is not None else None


class PostgreSQLAdapter(BaseDatabaseAdapter):
    engine_type = DatabaseEngine.POSTGRESQL

    def list_procedures(self) -> list[str]:
        try:
            return inspect(self.engine).get_function_names() or []
        except Exception:
            return []

    def get_procedure_definition(self, procedure_name: str) -> str:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT pg_get_functiondef(p.oid) "
                    "FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid "
                    "WHERE p.proname=:name LIMIT 1"
                ),
                {"name": procedure_name},
            ).first()
            return row[0] if row and row[0] else ""

    def get_version(self) -> str:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT version()")).scalar() or "unknown"

    def estimate_table_rows(self, table_name: str) -> int | None:
        with self.engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT reltuples::bigint "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relname = :name AND c.relkind IN ('r', 'p') "
                    "ORDER BY CASE WHEN n.nspname = current_schema() THEN 0 ELSE 1 END "
                    "LIMIT 1"
                ),
                {"name": table_name.strip("`[]\"").split(".")[-1]},
            ).scalar()
            return int(value) if value is not None and int(value) >= 0 else None


class SQLServerAdapter(BaseDatabaseAdapter):
    engine_type = DatabaseEngine.SQL_SERVER

    def list_procedures(self) -> list[str]:
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sys.objects WHERE type='P' AND schema_id=SCHEMA_ID('dbo')"))
            return [row[0] for row in result.fetchall()]

    def get_procedure_definition(self, procedure_name: str) -> str:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT OBJECT_DEFINITION(OBJECT_ID(:name))"), {"name": procedure_name}).first()
            return row[0] if row and row[0] else ""

    def get_version(self) -> str:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT @@VERSION")).scalar() or "unknown"

    def estimate_table_rows(self, table_name: str) -> int | None:
        with self.engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT SUM(row_count) "
                    "FROM sys.dm_db_partition_stats "
                    "WHERE object_id = OBJECT_ID(:name) AND index_id IN (0, 1)"
                ),
                {"name": table_name.strip("`[]\"")},
            ).scalar()
            return int(value) if value is not None else None

    def explain_query(self, sql: str) -> list[dict[str, Any]]:
        stripped = sql.strip().rstrip(";")
        if stripped.lower().startswith("explain"):
            stripped = re.sub(r"^\s*explain\s+", "", stripped, count=1, flags=re.I)
        if not stripped.lower().startswith("select"):
            raise DomainError("SQL Server plan analysis is only supported for SELECT statements")
        with self.engine.connect() as conn:
            result = conn.execute(text(f"SET SHOWPLAN_TEXT ON; {stripped}; SET SHOWPLAN_TEXT OFF;"))
            return [dict(row._mapping) for row in result.fetchall()]

    def apply_limit(self, sql: str, limit: int) -> str:
        stripped = sql.strip().rstrip(";")
        lowered = stripped.lower()
        if not lowered.startswith("select") or _has_limit_clause(lowered):
            return stripped
        return re.sub(r"^\s*select\b", f"SELECT TOP {limit}", stripped, count=1, flags=re.I)


class SQLiteAdapter(BaseDatabaseAdapter):
    engine_type = DatabaseEngine.SQLITE

    def get_version(self) -> str:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT sqlite_version()")).scalar() or "unknown"

    def explain_query(self, sql: str) -> list[dict[str, Any]]:
        stripped = sql.strip().rstrip(";")
        if stripped.lower().startswith("explain"):
            stripped = re.sub(r"^\s*explain\s+", "", stripped, count=1, flags=re.I)
        with self.engine.connect() as conn:
            result = conn.execute(text(f"EXPLAIN QUERY PLAN {stripped}"))
            return [dict(row._mapping) for row in result.fetchall()]


class OracleAdapter(BaseDatabaseAdapter):
    engine_type = DatabaseEngine.ORACLE

    def get_version(self) -> str:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT * FROM v$version WHERE ROWNUM = 1")).scalar() or "unknown"

    def apply_limit(self, sql: str, limit: int) -> str:
        stripped = sql.strip().rstrip(";")
        lowered = stripped.lower()
        if not lowered.startswith("select") or _has_limit_clause(lowered):
            return stripped
        return f"{stripped} FETCH FIRST {limit} ROWS ONLY"


def adapter_for(engine_type: DatabaseEngine, engine: Engine) -> BaseDatabaseAdapter:
    if engine_type == DatabaseEngine.MYSQL:
        return MySQLAdapter(engine)
    if engine_type == DatabaseEngine.POSTGRESQL:
        return PostgreSQLAdapter(engine)
    if engine_type == DatabaseEngine.SQL_SERVER:
        return SQLServerAdapter(engine)
    if engine_type == DatabaseEngine.SQLITE:
        return SQLiteAdapter(engine)
    if engine_type == DatabaseEngine.ORACLE:
        return OracleAdapter(engine)
    raise DomainError(f"Unsupported database engine: {engine_type}")


def _has_limit_clause(lowered_sql: str) -> bool:
    return any(token in lowered_sql for token in (" limit ", " top ", " fetch first ", " offset "))
