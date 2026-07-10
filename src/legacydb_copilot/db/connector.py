from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError

from legacydb_copilot.common import DomainError
from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.db.adapters import BaseDatabaseAdapter, adapter_for

logger = logging.getLogger(__name__)


def _normalize_mysql_ssl_options(connection_string: str) -> tuple[str, dict[str, Any]]:
    """Translate common MySQL URL SSL flags into PyMySQL connect_args.

    PyMySQL expects the ``ssl`` option to be a dictionary. If the URL contains
    ``?ssl=true`` or ``?ssl-mode=require``, SQLAlchemy passes a string through
    to PyMySQL, which raises ``'str' object has no attribute 'get'``.
    """

    url = make_url(connection_string)
    query = dict(url.query)
    ssl_requested = False
    for key in ("ssl", "ssl_mode", "ssl-mode"):
        value = query.pop(key, None)
        if value is None:
            continue
        ssl_requested = str(value).lower() in {"1", "true", "yes", "on", "require", "required"}
    if not ssl_requested:
        return connection_string, {}
    return url.set(query=query).render_as_string(hide_password=False), {"ssl": {}}


class DatabaseConnectionError(DomainError):
    """Raised when database connection fails."""

    pass


class SchemaMetadata:
    """Container for database schema information."""

    def __init__(
        self,
        engine_type: str,
        tables: list[str],
        views: list[str],
        procedures: list[str],
        version: str,
    ):
        self.engine_type = engine_type
        self.tables = tables
        self.views = views
        self.procedures = procedures
        self.version = version

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine_type,
            "tables": self.tables,
            "views": self.views,
            "procedures": self.procedures,
            "version": self.version,
        }


class DatabaseConnector:
    """Manages connections to external databases."""

    def __init__(self, database_engine: DatabaseEngine, connection_string: str):
        self.database_engine = database_engine
        self.connection_string = connection_string
        self._engine: Engine | None = None
        self._adapter: BaseDatabaseAdapter | None = None

    def _build_connection_config(self) -> tuple[str, dict[str, Any]]:
        """Build SQLAlchemy connection string and driver options based on engine type."""
        if self.database_engine == DatabaseEngine.MYSQL:
            # Use pymysql as the driver
            connection_string = self.connection_string
            if not self.connection_string.startswith("mysql+pymysql://"):
                if self.connection_string.startswith("mysql://"):
                    connection_string = self.connection_string.replace("mysql://", "mysql+pymysql://", 1)
            return _normalize_mysql_ssl_options(connection_string)
        return self.connection_string, {}

    def connect(self) -> None:
        """Establish connection to the database."""
        try:
            conn_string, connect_args = self._build_connection_config()
            self._engine = create_engine(
                conn_string,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args=connect_args,
                echo=False,
            )
            # Test the connection
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._adapter = adapter_for(self.database_engine, self._engine)
            logger.info(f"Connected to {self.database_engine} database")
        except Exception as exc:
            if self._engine:
                self._engine.dispose()
                self._engine = None
                self._adapter = None
            raise DatabaseConnectionError(f"Failed to connect to database: {str(exc)}") from exc

    def disconnect(self) -> None:
        """Close the database connection."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._adapter = None

    def get_engine(self) -> Engine:
        """Get the SQLAlchemy engine, connecting if necessary."""
        if self._engine is None:
            self.connect()
        return self._engine

    def get_adapter(self) -> BaseDatabaseAdapter:
        """Get the database-specific adapter, connecting if necessary."""
        engine = self.get_engine()
        if self._adapter is None:
            self._adapter = adapter_for(self.database_engine, engine)
        return self._adapter

    def test_connection(self) -> bool:
        """Test if the database connection is valid."""
        try:
            with self.get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_schema_metadata(self) -> SchemaMetadata:
        """Extract schema metadata from the database."""
        try:
            adapter = self.get_adapter()

            # Get tables
            tables = adapter.list_tables()

            # Get views
            views = adapter.list_views()

            # Get stored procedures (engine-specific)
            procedures = self.list_procedures()

            # Get version
            version = adapter.get_version()

            return SchemaMetadata(
                engine_type=self.database_engine.value,
                tables=tables,
                views=views,
                procedures=procedures,
                version=version,
            )
        except Exception as exc:
            raise DatabaseConnectionError(f"Failed to extract schema metadata: {str(exc)}") from exc

    def get_table_schema(self, table_name: str) -> dict[str, Any]:
        """Get detailed schema for a specific table."""
        try:
            adapter = self.get_adapter()

            if table_name not in adapter.list_tables():
                raise DomainError(f"Table not found: {table_name}")

            # Get columns
            columns = adapter.list_columns(table_name)
            # Get primary keys
            pk_constraint = adapter.get_primary_key(table_name)
            # Get foreign keys
            fk_constraints = adapter.list_foreign_keys(table_name)
            # Get indexes
            indexes = adapter.list_indexes(table_name)

            return {
                "table_name": table_name,
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col["nullable"],
                        "default": col.get("default"),
                    }
                    for col in columns
                ],
                "primary_key": pk_constraint.get("constrained_columns", []),
                "foreign_keys": [
                    {
                        "name": fk["name"],
                        "columns": fk["constrained_columns"],
                        "referred_table": fk["referred_table"],
                        "referred_columns": fk["referred_columns"],
                    }
                    for fk in fk_constraints
                ],
                "indexes": [
                    {
                        "name": idx["name"],
                        "columns": idx["column_names"],
                        "unique": idx["unique"],
                    }
                    for idx in indexes
                ],
            }
        except DomainError:
            raise
        except Exception as exc:
            raise DatabaseConnectionError(f"Failed to get table schema: {str(exc)}") from exc

    def execute_select_query(self, sql: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Execute a SELECT query safely with result limiting."""
        try:
            # Ensure it's a SELECT query
            query_upper = sql.strip().upper()
            if not query_upper.startswith("SELECT"):
                raise DomainError("Only SELECT queries are allowed")

            return self.get_adapter().execute_read_only_query(sql, limit)
        except DomainError:
            raise
        except Exception as exc:
            raise DatabaseConnectionError(f"Query execution failed: {str(exc)}") from exc

    def execute_read_only_query(self, sql: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Execute a read-only statement through the database adapter."""
        try:
            query_upper = sql.strip().upper()
            if not query_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN")):
                raise DomainError("Only read-only queries are allowed")
            if query_upper.startswith("EXPLAIN"):
                return self.explain_query(sql)
            return self.get_adapter().execute_read_only_query(sql, limit)
        except DomainError:
            raise
        except Exception as exc:
            raise DatabaseConnectionError(f"Query execution failed: {str(exc)}") from exc

    def estimate_table_rows(self, table_name: str) -> int | None:
        """Return a cheap metadata row estimate when the database engine exposes one."""
        try:
            return self.get_adapter().estimate_table_rows(table_name)
        except Exception:
            return None

    def _get_stored_procedures(self, inspector: Any, engine: Engine) -> list[str]:
        """Get stored procedures from the database (engine-specific)."""
        try:
            return self.list_procedures()
        except Exception as exc:
            logger.warning(f"Could not retrieve stored procedures: {exc}")
            return []

    def _get_database_version(self, engine: Engine) -> str:
        """Get database version."""
        try:
            return self.get_adapter().get_version()
        except Exception:
            return "unknown"

    def list_procedures(self) -> list[str]:
        try:
            return self.get_adapter().list_procedures()
        except Exception as exc:
            logger.warning(f"Could not retrieve stored procedures: {exc}")
            return []

    def get_procedure_definition(self, procedure_name: str) -> str:
        try:
            return self.get_adapter().get_procedure_definition(procedure_name)
        except Exception as exc:
            logger.warning(f"Could not retrieve procedure definition for {procedure_name}: {exc}")
            return ""

    def explain_query(self, sql: str) -> list[dict[str, Any]]:
        return self.get_adapter().explain_query(sql)


class ConnectionPool:
    """Manages a pool of database connections."""

    def __init__(self):
        self._connections: dict[str, DatabaseConnector] = {}
        self._cache_keys: dict[str, str] = {}

    def get_or_create(self, connection_id: str, database_engine: DatabaseEngine, connection_string: str) -> DatabaseConnector:
        """Get or create a connection."""
        cache_key = self.connector_cache_key(database_engine, connection_string)
        existing = self._connections.get(connection_id)
        if existing and (
            existing.database_engine != database_engine
            or existing.connection_string != connection_string
            or self._cache_keys.get(connection_id) != cache_key
        ):
            existing.disconnect()
            del self._connections[connection_id]
            self._cache_keys.pop(connection_id, None)

        if connection_id not in self._connections:
            self._connections[connection_id] = DatabaseConnector(database_engine, connection_string)
            self._cache_keys[connection_id] = cache_key
        return self._connections[connection_id]

    def connector_cache_key(self, database_engine: DatabaseEngine, connection_string: str) -> str:
        url = make_url(connection_string)
        return "|".join(
            [
                database_engine.value,
                url.host or "",
                str(url.port or ""),
                url.database or "",
                url.username or "",
                connection_string,
            ]
        )

    def close(self, connection_id: str) -> None:
        """Close a specific connection."""
        if connection_id in self._connections:
            self._connections[connection_id].disconnect()
            del self._connections[connection_id]
            self._cache_keys.pop(connection_id, None)

    def close_all(self) -> None:
        """Close all connections."""
        for connector in self._connections.values():
            connector.disconnect()
        self._connections.clear()
        self._cache_keys.clear()


# Global connection pool
_pool = ConnectionPool()


def get_connection_pool() -> ConnectionPool:
    """Get the global connection pool."""
    return _pool
