from __future__ import annotations

from abc import ABC
import re
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from legacydb_copilot.common import DomainError
from legacydb_copilot.databases import DatabaseEngine


class BaseDatabaseAdapter(ABC):
    """
    Owner: Mukesh Dabi
    Purpose:
        Provides the database-engine abstraction used by metadata discovery and safe read-only evidence collection.

    Input:
        SQLAlchemy engine for a target customer database.

    Output:
        Generic metadata, procedure definitions, EXPLAIN output, row estimates, and read-only query results.

    Called by:
        Database connector factory, metadata search, evidence collector, and verification agent.

    Flow:
        Database connection -> adapter_for(engine) -> metadata/procedure/read-only query APIs -> investigation engine.

    Safety:
        Adapters must not expose write helpers. Query execution paths are intended for SQL already approved by
        SafeSQLValidator.
    """

    engine_type: DatabaseEngine

    def __init__(self, engine: Engine):
        """
        Owner: Mukesh Dabi
        Purpose:
            Internal helper for init within adapters.py.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Internal callers in adapters.py.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        self.engine = engine

    def list_tables(self) -> list[str]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list tables within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return inspect(self.engine).get_table_names(schema=None)

    def list_views(self) -> list[str]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list views within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return inspect(self.engine).get_view_names(schema=None)

    def list_columns(self, table_name: str) -> list[dict[str, Any]]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list columns within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return inspect(self.engine).get_columns(table_name)

    def list_indexes(self, table_name: str) -> list[dict[str, Any]]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list indexes within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return inspect(self.engine).get_indexes(table_name)

    def list_foreign_keys(self, table_name: str) -> list[dict[str, Any]]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list foreign keys within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return inspect(self.engine).get_foreign_keys(table_name)

    def get_primary_key(self, table_name: str) -> dict[str, Any]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get primary key within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return inspect(self.engine).get_pk_constraint(table_name)

    def list_procedures(self) -> list[str]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list procedures within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return []

    def get_procedure_definition(self, procedure_name: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get procedure definition within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return ""

    def get_version(self) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get version within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return "unknown"

    def estimate_table_rows(self, table_name: str) -> int | None:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles estimate table rows within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        return None

    def explain_query(self, sql: str) -> list[dict[str, Any]]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles explain query within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        explain_sql = sql if sql.strip().lower().startswith("explain") else f"EXPLAIN {sql}"
        with self.engine.connect() as conn:
            result = conn.execute(text(explain_sql))
            return [dict(row._mapping) for row in result.fetchall()]

    def execute_read_only_query(self, sql: str, limit: int = 1000) -> list[dict[str, Any]]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles execute read only query within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        sql = self.apply_limit(sql, limit)
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row._mapping) for row in result.fetchall()]

    def apply_limit(self, sql: str, limit: int) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles apply limit within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        stripped = sql.strip().rstrip(";")
        lowered = stripped.lower()
        if not lowered.startswith("select") or _has_limit_clause(lowered):
            return stripped
        return f"{stripped} LIMIT {limit}"


class MySQLAdapter(BaseDatabaseAdapter):
    engine_type = DatabaseEngine.MYSQL

    def list_procedures(self) -> list[str]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list procedures within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES "
                    "WHERE ROUTINE_TYPE='PROCEDURE' AND ROUTINE_SCHEMA=DATABASE()"
                )
            )
            return [row[0] for row in result.fetchall()]

    def get_procedure_definition(self, procedure_name: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get procedure definition within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
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
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get version within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT VERSION()")).scalar() or "unknown"

    def estimate_table_rows(self, table_name: str) -> int | None:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles estimate table rows within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
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
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list procedures within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        try:
            return inspect(self.engine).get_function_names() or []
        except Exception:
            return []

    def get_procedure_definition(self, procedure_name: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get procedure definition within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
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
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get version within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT version()")).scalar() or "unknown"

    def estimate_table_rows(self, table_name: str) -> int | None:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles estimate table rows within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
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

    _SYSTEM_SCHEMAS = {"sys", "information_schema"}

    def _accessible_schemas(self) -> list[str]:
        """Return visible user schemas in deterministic order."""
        schemas = inspect(self.engine).get_schema_names()
        return sorted(
            {
                schema
                for schema in schemas
                if schema and schema.lower() not in self._SYSTEM_SCHEMAS
            },
            key=str.lower,
        )

    @staticmethod
    def _qualified_name(schema: str, object_name: str) -> str:
        return f"{schema}.{object_name}"

    @staticmethod
    def _split_qualified_name(object_name: str) -> tuple[str | None, str]:
        cleaned = (
            object_name.strip()
            .replace("[", "")
            .replace("]", "")
            .replace('"', "")
            .replace("`", "")
        )
        if "." not in cleaned:
            return None, cleaned
        schema, name = cleaned.split(".", 1)
        return schema, name

    def list_tables(self) -> list[str]:
        inspector = inspect(self.engine)
        return [
            self._qualified_name(schema, table)
            for schema in self._accessible_schemas()
            for table in sorted(inspector.get_table_names(schema=schema), key=str.lower)
        ]

    def list_views(self) -> list[str]:
        inspector = inspect(self.engine)
        views: list[str] = []
        for schema in self._accessible_schemas():
            try:
                schema_views = inspector.get_view_names(schema=schema)
            except NotImplementedError:
                schema_views = []
            views.extend(
                self._qualified_name(schema, view)
                for view in sorted(schema_views, key=str.lower)
            )
        return views

    def list_columns(self, table_name: str) -> list[dict[str, Any]]:
        schema, name = self._split_qualified_name(table_name)
        return inspect(self.engine).get_columns(name, schema=schema)

    def get_primary_key(self, table_name: str) -> dict[str, Any]:
        schema, name = self._split_qualified_name(table_name)
        return inspect(self.engine).get_pk_constraint(name, schema=schema)

    def list_foreign_keys(self, table_name: str) -> list[dict[str, Any]]:
        schema, name = self._split_qualified_name(table_name)
        foreign_keys = inspect(self.engine).get_foreign_keys(name, schema=schema)
        qualified: list[dict[str, Any]] = []
        for foreign_key in foreign_keys:
            item = dict(foreign_key)
            referred_schema = item.get("referred_schema") or schema
            referred_table = item.get("referred_table")
            if referred_schema and referred_table:
                item["referred_table"] = self._qualified_name(
                    str(referred_schema), str(referred_table)
                )
            qualified.append(item)
        return qualified

    def list_indexes(self, table_name: str) -> list[dict[str, Any]]:
        schema, name = self._split_qualified_name(table_name)
        return inspect(self.engine).get_indexes(name, schema=schema)

    def list_procedures(self) -> list[str]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles list procedures within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT SCHEMA_NAME(schema_id) AS schema_name, name "
                    "FROM sys.objects "
                    "WHERE type IN ('P', 'PC', 'FN', 'FS', 'FT', 'IF', 'TF', 'TR') "
                    "AND SCHEMA_NAME(schema_id) NOT IN ('sys', 'INFORMATION_SCHEMA') "
                    "ORDER BY schema_name, name"
                )
            )
            return [self._qualified_name(row[0], row[1]) for row in result.fetchall()]

    def get_procedure_definition(self, procedure_name: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get procedure definition within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT OBJECT_DEFINITION(OBJECT_ID(:name))"), {"name": procedure_name}).first()
            return row[0] if row and row[0] else ""

    def get_version(self) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get version within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT @@VERSION")).scalar() or "unknown"

    def estimate_table_rows(self, table_name: str) -> int | None:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles estimate table rows within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
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
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles explain query within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        stripped = sql.strip().rstrip(";")
        if stripped.lower().startswith("explain"):
            stripped = re.sub(r"^\s*explain\s+", "", stripped, count=1, flags=re.I)
        if not stripped.lower().startswith("select"):
            raise DomainError("SQL Server plan analysis is only supported for SELECT statements")
        with self.engine.connect() as conn:
            result = conn.execute(text(f"SET SHOWPLAN_TEXT ON; {stripped}; SET SHOWPLAN_TEXT OFF;"))
            return [dict(row._mapping) for row in result.fetchall()]

    def apply_limit(self, sql: str, limit: int) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles apply limit within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        stripped = sql.strip().rstrip(";")
        lowered = stripped.lower()
        if not lowered.startswith("select") or _has_limit_clause(lowered):
            return stripped
        return re.sub(r"^\s*select\b", f"SELECT TOP {limit}", stripped, count=1, flags=re.I)


class SQLiteAdapter(BaseDatabaseAdapter):
    engine_type = DatabaseEngine.SQLITE

    def get_version(self) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get version within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT sqlite_version()")).scalar() or "unknown"

    def explain_query(self, sql: str) -> list[dict[str, Any]]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles explain query within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        stripped = sql.strip().rstrip(";")
        if stripped.lower().startswith("explain"):
            stripped = re.sub(r"^\s*explain\s+", "", stripped, count=1, flags=re.I)
        with self.engine.connect() as conn:
            result = conn.execute(text(f"EXPLAIN QUERY PLAN {stripped}"))
            return [dict(row._mapping) for row in result.fetchall()]


class OracleAdapter(BaseDatabaseAdapter):
    engine_type = DatabaseEngine.ORACLE

    def get_version(self) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get version within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT * FROM v$version WHERE ROWNUM = 1")).scalar() or "unknown"

    def apply_limit(self, sql: str, limit: int) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles apply limit within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Application services that need this abstraction.
        
        Where it fits in the flow:
            Caller -> function -> structured return value for the next application step.
        
        Safety considerations:
            Must preserve read-only investigation behavior and avoid modifying customer databases.
        """
        stripped = sql.strip().rstrip(";")
        lowered = stripped.lower()
        if not lowered.startswith("select") or _has_limit_clause(lowered):
            return stripped
        return f"{stripped} FETCH FIRST {limit} ROWS ONLY"


def adapter_for(engine_type: DatabaseEngine, engine: Engine) -> BaseDatabaseAdapter:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles adapter for within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Application services that need this abstraction.
    
    Where it fits in the flow:
        Caller -> function -> structured return value for the next application step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for has limit clause within adapters.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in adapters.py.
    
    Where it fits in the flow:
        Caller -> function -> structured return value for the next application step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    return any(token in lowered_sql for token in (" limit ", " top ", " fetch first ", " offset "))
