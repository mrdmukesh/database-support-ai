from __future__ import annotations

import os

from sqlalchemy.engine import make_url

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
    validated: dict[str, str] = {}
    for domain, database in AZURE_EVALUATION_DATABASES.items():
        variable = f"EVAL_APP_SQL_URL_{domain}"
        secret = os.getenv(variable, "")
        connection_id = os.getenv(f"EVAL_CONNECTION_ID_{domain}", "")
        if not secret or not connection_id:
            raise RuntimeError(
                f"Azure evaluation configuration is incomplete for {domain.casefold()}"
            )
        url = make_url(secret)
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
