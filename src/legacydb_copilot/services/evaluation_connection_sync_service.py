from __future__ import annotations

import os

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
