from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from legacydb_copilot.ai import SafetyFinding, analyze_prompt
from legacydb_copilot.common import DomainError


class DatabaseEngine(StrEnum):
    SQL_SERVER = "sql_server"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    ORACLE = "oracle"


@dataclass(frozen=True)
class DatabaseConnector:
    engine: DatabaseEngine
    display_name: str
    supports_metadata_extraction: bool
    plugin_name: str | None = None


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[DatabaseEngine, DatabaseConnector] = {}

    def register(self, connector: DatabaseConnector) -> None:
        if connector.engine in self._connectors:
            raise DomainError(f"Connector already registered: {connector.engine}")
        self._connectors[connector.engine] = connector

    def get(self, engine: DatabaseEngine) -> DatabaseConnector:
        try:
            return self._connectors[engine]
        except KeyError as exc:
            raise DomainError(f"Connector is not registered: {engine}") from exc

    def list_engines(self) -> tuple[DatabaseEngine, ...]:
        return tuple(self._connectors)


def default_connector_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(DatabaseConnector(DatabaseEngine.SQL_SERVER, "SQL Server", True))
    registry.register(DatabaseConnector(DatabaseEngine.POSTGRESQL, "PostgreSQL", True))
    registry.register(DatabaseConnector(DatabaseEngine.MYSQL, "MySQL", True))
    registry.register(DatabaseConnector(DatabaseEngine.SQLITE, "SQLite", True))
    registry.register(DatabaseConnector(DatabaseEngine.ORACLE, "Oracle", False, "oracle"))
    return registry


def validate_sql_for_execution(sql: str) -> None:
    report = analyze_prompt(sql)
    if SafetyFinding.UNSAFE_SQL in report.findings:
        raise DomainError("Unsafe SQL requires explicit human approval")
