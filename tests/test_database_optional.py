from __future__ import annotations

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.connector import DatabaseConnector
from legacydb_copilot.db.models import OrganizationModel, WorkspaceModel
from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.routers.databases import _looks_like_connection_string


def test_sqlalchemy_models_create_tenant_tables_in_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    tables = set(inspect(engine).get_table_names())

    assert "organizations" in tables
    assert "workspaces" in tables
    assert "documents" in tables
    assert "incidents" in tables
    assert "subscriptions" in tables


def test_workspace_has_org_foreign_key_shape() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        org = OrganizationModel(name="Acme", slug="acme")
        session.add(org)
        session.flush()
        session.add(WorkspaceModel(organization_id=org.id, name="Finance", slug="finance"))
        session.commit()

        workspace = session.query(WorkspaceModel).one()
        assert workspace.organization_id == org.id


def test_mysql_connection_string_is_normalized_for_sqlalchemy() -> None:
    connector = DatabaseConnector(
        DatabaseEngine.MYSQL,
        "mysql://user:password@localhost:3306/legacy",
    )

    connection_string, connect_args = connector._build_connection_config()

    assert connection_string == "mysql+pymysql://user:password@localhost:3306/legacy"
    assert connect_args == {}


def test_mysql_ssl_query_parameter_becomes_pymysql_connect_args() -> None:
    connector = DatabaseConnector(
        DatabaseEngine.MYSQL,
        "mysql://appadmin:secret@example.mysql.database.azure.com:3306/clinic_ops_ai_demo?ssl=true",
    )

    connection_string, connect_args = connector._build_connection_config()

    assert connection_string == "mysql+pymysql://appadmin:secret@example.mysql.database.azure.com:3306/clinic_ops_ai_demo"
    assert connect_args == {"ssl": {}}


def test_secret_manager_reference_is_not_treated_as_connection_string() -> None:
    assert not _looks_like_connection_string("secret-manager://legacy-erp/prod")
