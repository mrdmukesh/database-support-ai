from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import DatabaseConnectionModel
from legacydb_copilot.db.session import create_session_factory

SERVER = "sql-dsai-eval-56ab486d.database.windows.net"
READER = "legacydb_eval_reader"
DATABASES = {
    "PAYROLL": "EvalPayroll",
    "CLINIC": "EvalClinic",
    "ORDERS": "EvalOrders",
    "BANKING": "EvalBanking",
    "SHIPPING": "EvalShipping",
}
WRITE_PERMISSIONS = {"INSERT", "UPDATE", "DELETE", "EXECUTE"}


def validate_connection(domain: str, database: str) -> dict[str, object]:
    variable = f"EVAL_APP_SQL_URL_{domain}"
    configured = os.environ.get(variable, "")
    if not configured:
        raise RuntimeError(f"{variable} is not configured")
    url = make_url(configured)
    if (
        url.host != SERVER
        or (url.port or 1433) != 1433
        or url.database != database
        or url.username != READER
    ):
        raise RuntimeError(f"{variable} does not match the approved Azure reader identity")
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        identity = connection.execute(
            text(
                "SELECT @@SERVERNAME, DB_NAME(), ORIGINAL_LOGIN(), "
                "SUSER_SNAME(), USER_NAME()"
            )
        ).one()
        metadata_counts = connection.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM sys.tables),"
                "(SELECT COUNT(*) FROM sys.columns),"
                "(SELECT COUNT(*) FROM sys.schemas),"
                "(SELECT COUNT(*) FROM sys.procedures),"
                "(SELECT COUNT(*) FROM sys.sql_modules),"
                "(SELECT COUNT(*) FROM sys.foreign_keys),"
                "(SELECT COUNT(*) FROM sys.indexes)"
            )
        ).one()
        permission_rows = connection.execute(
            text(
                "SELECT permission_name, state_desc FROM sys.database_permissions "
                "WHERE grantee_principal_id=USER_ID() "
                "AND permission_name IN ('INSERT','UPDATE','DELETE','EXECUTE')"
            )
        ).all()
        role_rows = connection.execute(
            text(
                "SELECT role_principal.name FROM sys.database_role_members drm "
                "JOIN sys.database_principals role_principal "
                "ON role_principal.principal_id=drm.role_principal_id "
                "WHERE drm.member_principal_id=USER_ID()"
            )
        ).all()
    granted_writes = {
        permission
        for permission, state in permission_rows
        if permission in WRITE_PERMISSIONS and state.startswith("GRANT")
    }
    if granted_writes or "db_datareader" not in {row[0] for row in role_rows}:
        raise RuntimeError(f"{variable} is not least privilege")
    if identity[1] != database or identity[2] != READER or identity[4] != READER:
        raise RuntimeError(f"{variable} returned an unexpected database identity")
    return {
        "domain": domain.casefold(),
        "server": identity[0],
        "host": url.host,
        "port": url.port or 1433,
        "database": identity[1],
        "login": identity[2],
        "server_login": identity[3],
        "database_user": identity[4],
        "metadata_counts": tuple(metadata_counts),
        "write_grants": sorted(granted_writes),
        "secret_reference": f"env://{variable}",
    }


def apply_records() -> None:
    session_factory = create_session_factory(Settings.from_env().database_url)
    with session_factory() as db:
        for domain, database in DATABASES.items():
            connection_id = os.environ.get(f"EVAL_CONNECTION_ID_{domain}", "")
            record = db.get(DatabaseConnectionModel, connection_id)
            if record is None:
                raise RuntimeError(f"Missing application connection for {domain.casefold()}")
            record.engine = "sql_server"
            record.host = SERVER
            record.port = 1433
            record.database_name = database
            record.secret_ref = f"env://EVAL_APP_SQL_URL_{domain}"
            record.environment_type = "evaluation"
            record.is_active = True
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    results = [
        validate_connection(domain, database)
        for domain, database in DATABASES.items()
    ]
    if args.apply:
        apply_records()
    for result in results:
        print(
            "|".join(
                (
                    f"domain={result['domain']}",
                    f"server={result['server']}",
                    f"host={result['host']}",
                    f"port={result['port']}",
                    f"database={result['database']}",
                    f"login={result['login']}",
                    f"database_user={result['database_user']}",
                    f"metadata_counts={result['metadata_counts']}",
                    f"write_grants={result['write_grants']}",
                    f"secret_reference={result['secret_reference']}",
                )
            )
        )
    print(f"records_updated={args.apply}")


if __name__ == "__main__":
    main()
