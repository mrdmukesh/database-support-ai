from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import DatabaseConnectionModel
from legacydb_copilot.db.session import create_session_factory

AZURE_EVALUATION_SERVER = "sql-dsai-eval-56ab486d.database.windows.net"
AZURE_EVALUATION_READER = "legacydb_eval_reader"
AZURE_EVALUATION_DATABASES = {
    "PAYROLL": "EvalPayroll",
    "CLINIC": "EvalClinic",
    "ORDERS": "EvalOrders",
    "BANKING": "EvalBanking",
    "SHIPPING": "EvalShipping",
}


@dataclass(frozen=True)
class AzureReaderValidation:
    domain: str
    server: str
    port: int
    database: str
    login: str
    database_user: str
    metadata_objects: int
    select_allowed: bool
    write_allowed: bool


def evaluation_connection_sync_enabled() -> bool:
    return os.getenv("EVALUATION_AZURE_CONNECTION_SYNC_ENABLED", "false").casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def sync_azure_evaluation_connections(settings: Settings | None = None) -> int:
    """Persist only approved identities and environment secret references."""
    if not evaluation_connection_sync_enabled():
        return 0
    resolved = settings or Settings.from_env()
    reader_password = os.getenv("EVAL_READER_PASSWORD", "")
    validated: dict[str, str] = {}
    for domain, database in AZURE_EVALUATION_DATABASES.items():
        variable = f"EVAL_APP_SQL_URL_{domain}"
        secret = os.getenv(variable, "")
        connection_id = os.getenv(f"EVAL_CONNECTION_ID_{domain}", "")
        try:
            url = make_url(secret)
        except ArgumentError:
            url = None
        if url is None and reader_password:
            url = URL.create(
                "mssql+pyodbc",
                username=AZURE_EVALUATION_READER,
                password=reader_password,
                host=AZURE_EVALUATION_SERVER,
                port=1433,
                database=database,
                query={
                    "driver": "ODBC Driver 18 for SQL Server",
                    "Encrypt": "yes",
                    "TrustServerCertificate": "no",
                },
            )
            # Keep the credential process-local. Only the env:// reference is persisted.
            os.environ[variable] = url.render_as_string(hide_password=False)
        if url is None or not connection_id:
            raise RuntimeError(
                f"Azure evaluation configuration is incomplete for {domain.casefold()}"
            )
        if (
            url.host != AZURE_EVALUATION_SERVER
            or (url.port or 1433) != 1433
            or url.database != database
            or url.username != AZURE_EVALUATION_READER
            or not url.password
        ):
            raise RuntimeError(
                f"Azure evaluation secret identity is invalid for {domain.casefold()}"
            )
        validated[domain] = connection_id

    validate_azure_evaluation_connections()
    session_factory = create_session_factory(resolved.database_url)
    with session_factory() as db:
        for domain, connection_id in validated.items():
            record = db.get(DatabaseConnectionModel, connection_id)
            if record is None:
                raise RuntimeError(
                    f"Azure evaluation connection record is missing for {domain.casefold()}"
                )
            record.engine = "sql_server"
            record.host = AZURE_EVALUATION_SERVER
            record.port = 1433
            record.database_name = AZURE_EVALUATION_DATABASES[domain]
            record.secret_ref = f"env://EVAL_APP_SQL_URL_{domain}"
            record.environment_type = "evaluation"
            record.is_active = True
        db.commit()
    return len(validated)


def validate_azure_evaluation_connections() -> tuple[AzureReaderValidation, ...]:
    """Exercise each approved reader without exposing its connection string."""
    results = []
    for domain, expected_database in AZURE_EVALUATION_DATABASES.items():
        url = make_url(os.environ[f"EVAL_APP_SQL_URL_{domain}"])
        with create_engine(url, pool_pre_ping=True).connect() as connection:
            identity = connection.execute(
                text("SELECT DB_NAME(), ORIGINAL_LOGIN(), USER_NAME()")
            ).one()
            metadata_objects = int(
                connection.execute(
                    text(
                        "SELECT "
                        "(SELECT COUNT(*) FROM sys.tables) + "
                        "(SELECT COUNT(*) FROM sys.columns) + "
                        "(SELECT COUNT(*) FROM sys.schemas) + "
                        "(SELECT COUNT(*) FROM sys.foreign_keys) + "
                        "(SELECT COUNT(*) FROM sys.indexes)"
                    )
                ).scalar_one()
            )
            (
                select_allowed,
                insert_allowed,
                update_allowed,
                delete_allowed,
                execute_allowed,
                alter_allowed,
                control_allowed,
            ) = (
                bool(value)
                for value in connection.execute(
                    text(
                        "SELECT "
                        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'SELECT'), "
                        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'INSERT'), "
                        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'UPDATE'), "
                        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'DELETE'), "
                        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'EXECUTE'), "
                        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'ALTER'), "
                        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CONTROL')"
                    )
                ).one()
            )
        write_allowed = any(
            (
                insert_allowed,
                update_allowed,
                delete_allowed,
                execute_allowed,
                alter_allowed,
                control_allowed,
            )
        )
        if (
            url.host != AZURE_EVALUATION_SERVER
            or (url.port or 1433) != 1433
            or identity[0] != expected_database
            or identity[1] != AZURE_EVALUATION_READER
            or identity[2] != AZURE_EVALUATION_READER
            or metadata_objects <= 0
            or not select_allowed
            or write_allowed
        ):
            raise RuntimeError(
                f"Azure evaluation reader validation failed for {domain.casefold()}"
            )
        results.append(
            AzureReaderValidation(
                domain=domain.casefold(),
                server=url.host or "",
                port=url.port or 1433,
                database=identity[0],
                login=identity[1],
                database_user=identity[2],
                metadata_objects=metadata_objects,
                select_allowed=select_allowed,
                write_allowed=write_allowed,
            )
        )
    return tuple(results)


def main() -> None:
    sync_azure_evaluation_connections()
    for result in validate_azure_evaluation_connections():
        print(asdict(result))


if __name__ == "__main__":
    main()
