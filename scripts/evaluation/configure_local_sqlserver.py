from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.cli.__main__ import _load_local_evaluation_env, required_env
from evaluation.local_environment import _update_env
from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import DatabaseConnectionModel
from legacydb_copilot.db.session import create_session_factory


DATABASES = {"payroll":"EvalPayroll","clinic":"EvalClinic","orders":"EvalOrders","banking":"EvalBanking","shipping":"EvalShipping"}


def main() -> None:
    _load_local_evaluation_env()
    password = required_env("EVAL_SQL_PASSWORD")
    encoded = quote_plus(password)
    env_path = Path(os.getenv("EVAL_ENV_FILE", ".env.evaluation"))
    updates = {
        "EVAL_DATABASE_ENGINE":"sql_server", "EVAL_SQL_SERVER":"127.0.0.1,14333",
        "EVAL_ALLOWED_SQL_HOSTS":"127.0.0.1,localhost", "EVAL_ALLOWED_DATABASES":",".join(DATABASES.values()),
        "LOCAL_SQLSERVER_HOST":"127.0.0.1", "LOCAL_SQLSERVER_PORT":"14333",
    }
    for domain,database in DATABASES.items():
        key=f"EVAL_APP_SQLSERVER_SECRET_{domain.upper()}"
        updates[key]=f"mssql+pyodbc://evalreader:{encoded}@127.0.0.1:14333/{database}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes"
    with create_session_factory(Settings.from_env().database_url)() as db:
        ids={domain:required_env(f"EVAL_CONNECTION_ID_{domain.upper()}") for domain in DATABASES}
        for domain,database in DATABASES.items():
            record=db.get(DatabaseConnectionModel,ids[domain])
            if record is None: raise RuntimeError(f"Missing application connection for {domain}")
            record.engine="sql_server"; record.host="127.0.0.1"; record.port=14333
            record.database_name=database; record.secret_ref=f"env://EVAL_APP_SQLSERVER_SECRET_{domain.upper()}"; record.is_active=True
        db.commit()
    _update_env(env_path,updates)
    print("Configured five application connections for native local SQL Server; secrets were not printed.")


if __name__ == "__main__": main()
