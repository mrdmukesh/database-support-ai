from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from evaluation.runners.mysql_database import translate_tsql_batch
from legacydb_copilot.auth import Role
from legacydb_copilot.db.models import (
    DatabaseConnectionModel,
    OrganizationModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)
from legacydb_copilot.security import hash_password


DOMAINS = ("banking", "orders", "shipping", "payroll", "clinic")
DATABASES = {
    "app": "legacydb_app",
    "results": "legacydb_evaluation",
    **{domain: f"eval_{domain}" for domain in DOMAINS},
}


def _admin_connection(database: str | None = None):
    return pymysql.connect(
        host=os.environ["LOCAL_MYSQL_HOST"],
        port=int(os.getenv("LOCAL_MYSQL_PORT", "3306")),
        user=os.environ["LOCAL_MYSQL_ADMIN"],
        password=os.environ["LOCAL_MYSQL_PASSWORD"],
        database=database,
        autocommit=True,
        charset="utf8mb4",
    )


def _env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _update_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    output: list[str] = []
    for line in lines:
        name = line.split("=", 1)[0].strip() if "=" in line else ""
        if name in remaining:
            output.append(f"{name}={remaining.pop(name)}")
        else:
            output.append(line)
    if remaining:
        output.extend(["", "# Generated local MySQL evaluation environment"])
        output.extend(f"{name}={value}" for name, value in remaining.items())
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def provision(env_path: Path) -> None:
    current = _env_values(env_path)
    credentials = {
        "LOCAL_APP_DB_USER": current.get("LOCAL_APP_DB_USER", "legacydb_local_app"),
        "LOCAL_APP_DB_PASSWORD": current.get("LOCAL_APP_DB_PASSWORD") or secrets.token_urlsafe(24),
        "LOCAL_EVAL_DB_USER": current.get("LOCAL_EVAL_DB_USER", "legacydb_local_eval"),
        "LOCAL_EVAL_DB_PASSWORD": current.get("LOCAL_EVAL_DB_PASSWORD") or secrets.token_urlsafe(24),
        "LOCAL_READER_DB_USER": current.get("LOCAL_READER_DB_USER", "legacydb_local_reader"),
        "LOCAL_READER_DB_PASSWORD": current.get("LOCAL_READER_DB_PASSWORD") or secrets.token_urlsafe(24),
    }
    with _admin_connection() as connection, connection.cursor() as cursor:
        for database in DATABASES.values():
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
        for user_key, password_key in (
            ("LOCAL_APP_DB_USER", "LOCAL_APP_DB_PASSWORD"),
            ("LOCAL_EVAL_DB_USER", "LOCAL_EVAL_DB_PASSWORD"),
            ("LOCAL_READER_DB_USER", "LOCAL_READER_DB_PASSWORD"),
        ):
            user = credentials[user_key].replace("'", "''")
            password = credentials[password_key].replace("'", "''")
            cursor.execute(f"CREATE USER IF NOT EXISTS '{user}'@'%' IDENTIFIED BY '{password}'")
            cursor.execute(f"ALTER USER '{user}'@'%' IDENTIFIED BY '{password}'")
        app_user = credentials["LOCAL_APP_DB_USER"]
        eval_user = credentials["LOCAL_EVAL_DB_USER"]
        reader = credentials["LOCAL_READER_DB_USER"]
        cursor.execute(f"GRANT ALL PRIVILEGES ON `{DATABASES['app']}`.* TO '{app_user}'@'%'")
        cursor.execute(f"GRANT ALL PRIVILEGES ON `{DATABASES['results']}`.* TO '{eval_user}'@'%'")
        for domain in DOMAINS:
            database = DATABASES[domain]
            cursor.execute(f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{eval_user}'@'%'")
            cursor.execute(f"GRANT SELECT ON `{database}`.* TO '{reader}'@'%'")
        cursor.execute("FLUSH PRIVILEGES")

    host = os.environ["LOCAL_MYSQL_HOST"]
    port = os.getenv("LOCAL_MYSQL_PORT", "3306")
    app_url = (
        f"mysql+pymysql://{quote_plus(credentials['LOCAL_APP_DB_USER'])}:"
        f"{quote_plus(credentials['LOCAL_APP_DB_PASSWORD'])}@{host}:{port}/{DATABASES['app']}"
    )
    results_url = (
        f"mysql+pymysql://{quote_plus(credentials['LOCAL_EVAL_DB_USER'])}:"
        f"{quote_plus(credentials['LOCAL_EVAL_DB_PASSWORD'])}@{host}:{port}/{DATABASES['results']}"
    )
    reader_secret = (
        f"{credentials['LOCAL_READER_DB_USER']}:{quote_plus(credentials['LOCAL_READER_DB_PASSWORD'])}"
    )
    updates = {
        **credentials,
        "DATABASE_URL": app_url,
        "EVAL_RESULTS_DATABASE_URL": results_url,
        "EVAL_DATABASE_ENGINE": "mysql",
        "EVAL_MYSQL_HOST": host,
        "EVAL_MYSQL_PORT": port,
        "EVAL_MYSQL_USER": credentials["LOCAL_EVAL_DB_USER"],
        "EVAL_MYSQL_PASSWORD": credentials["LOCAL_EVAL_DB_PASSWORD"],
        "EVAL_ALLOWED_MYSQL_HOSTS": "127.0.0.1,localhost",
        "EVAL_ALLOWED_DATABASES": ",".join(DATABASES[domain] for domain in DOMAINS),
        "EVAL_API_BASE_URL": "http://127.0.0.1:8000",
        "EVAL_SCENARIO_TIMEOUT_SECONDS": "180",
        "EVAL_APPLICATION_DB_ACCESS_MODE": "read_only",
        "EVAL_SERVICE_CLIENT_ID": current.get("EVAL_SERVICE_CLIENT_ID", "local-evaluation-worker"),
        "EVAL_SERVICE_CLIENT_SECRET": current.get("EVAL_SERVICE_CLIENT_SECRET") or secrets.token_urlsafe(32),
        "EVALUATION_SERVICE_CLIENT_ID": current.get("EVAL_SERVICE_CLIENT_ID", "local-evaluation-worker"),
        "EVALUATION_SERVICE_CLIENT_SECRET": current.get("EVAL_SERVICE_CLIENT_SECRET") or secrets.token_urlsafe(32),
    }
    # Both service prefixes must share the exact same generated secret.
    updates["EVALUATION_SERVICE_CLIENT_SECRET"] = updates["EVAL_SERVICE_CLIENT_SECRET"]
    for domain in DOMAINS:
        updates[f"EVAL_APP_MYSQL_SECRET_{domain.upper()}"] = reader_secret
    _update_env(env_path, updates)


def load_domain_baselines() -> None:
    for domain in DOMAINS:
        database = DATABASES[domain]
        with _admin_connection(database) as connection, connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            cursor.execute("SHOW TABLES")
            for (table,) in cursor.fetchall():
                cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            for filename in ("01_create.sql", "02_seed.sql"):
                path = Path("evaluation_databases") / domain / "sql" / filename
                for statement in translate_tsql_batch(path.read_text(encoding="utf-8")):
                    try:
                        cursor.execute(statement)
                    except pymysql.MySQLError as exc:
                        # Procedure/function/trigger batches are intentionally excluded; all
                        # table/index/data failures remain fatal.
                        raise RuntimeError(f"{domain}/{filename}: {statement[:120]}: {exc}") from exc


def bootstrap_application(env_path: Path) -> None:
    values = _env_values(env_path)
    engine = create_engine(values["DATABASE_URL"], pool_pre_ping=True)
    with Session(engine) as db:
        organization = db.query(OrganizationModel).filter_by(slug="local-evaluation").one_or_none()
        if organization is None:
            organization = OrganizationModel(name="Local Evaluation", slug="local-evaluation", is_active=True)
            db.add(organization)
            db.flush()
        workspace = db.query(WorkspaceModel).filter_by(
            organization_id=organization.id, slug="research-benchmark"
        ).one_or_none()
        if workspace is None:
            workspace = WorkspaceModel(
                organization_id=organization.id,
                name="Research Benchmark",
                slug="research-benchmark",
                is_active=True,
            )
            db.add(workspace)
            db.flush()
        user = db.query(UserModel).filter_by(
            organization_id=organization.id, email="evaluation@localhost"
        ).one_or_none()
        if user is None:
            user = UserModel(
                organization_id=organization.id,
                email="evaluation@localhost",
                password_hash=hash_password(secrets.token_urlsafe(24)),
                full_name="Local Evaluation Service",
                role=Role.ORG_ADMIN.value,
                is_active=True,
            )
            db.add(user)
            db.flush()
        membership = db.query(WorkspaceMembershipModel).filter_by(
            workspace_id=workspace.id, user_id=user.id
        ).one_or_none()
        if membership is None:
            db.add(WorkspaceMembershipModel(
                organization_id=organization.id,
                workspace_id=workspace.id,
                user_id=user.id,
                role="OWNER",
                is_active=True,
            ))
        connection_ids: dict[str, str] = {}
        for domain in DOMAINS:
            name = f"Local {domain.title()} Read Only"
            record = db.query(DatabaseConnectionModel).filter_by(
                workspace_id=workspace.id, name=name
            ).one_or_none()
            if record is None:
                record = DatabaseConnectionModel(
                    organization_id=organization.id,
                    workspace_id=workspace.id,
                    engine="mysql",
                    name=name,
                    host=values["LOCAL_MYSQL_HOST"],
                    port=int(values["LOCAL_MYSQL_PORT"]),
                    database_name=DATABASES[domain],
                    secret_ref=f"env://EVAL_APP_MYSQL_SECRET_{domain.upper()}",
                    is_active=True,
                )
                db.add(record)
                db.flush()
            connection_ids[domain] = record.id
        db.commit()
        updates = {
            "EVAL_ORGANIZATION_ID": organization.id,
            "EVAL_WORKSPACE_ID": workspace.id,
            "EVAL_USER_ID": user.id,
            "EVALUATION_SERVICE_ORGANIZATION_ID": organization.id,
            "EVALUATION_SERVICE_WORKSPACE_ID": workspace.id,
            "EVALUATION_SERVICE_USER_ID": user.id,
            **{f"EVAL_CONNECTION_ID_{domain.upper()}": value for domain, value in connection_ids.items()},
        }
    _update_env(env_path, updates)


def main() -> None:
    env_path = Path(os.getenv("EVAL_ENV_FILE", ".env.evaluation"))
    command = sys.argv[1]
    if command == "provision":
        provision(env_path)
    elif command == "load-domains":
        load_domain_baselines()
    elif command == "bootstrap-app":
        bootstrap_application(env_path)
    else:
        raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
