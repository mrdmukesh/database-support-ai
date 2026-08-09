from __future__ import annotations

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from legacydb_copilot.db.base import Base


def _run_alembic(action, config: Config, revision: str) -> None:
    """Run Alembic without leaking its logging reconfiguration into other tests."""
    existing = {
        name: logger.disabled
        for name, logger in logging.Logger.manager.loggerDict.items()
        if isinstance(logger, logging.Logger)
    }
    database_url = os.environ.pop("DATABASE_URL", None)
    try:
        action(config, revision)
    finally:
        if database_url is not None:
            os.environ["DATABASE_URL"] = database_url
        for name, disabled in existing.items():
            logger = logging.Logger.manager.loggerDict.get(name)
            if isinstance(logger, logging.Logger):
                logger.disabled = disabled


def _config(database: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    return config


def test_revision_graph_has_one_linear_head_after_verification_migration() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == ["0026"]
    metadata = script.get_revision("0026")
    verification = script.get_revision("0025")
    governed = script.get_revision("0024")
    assert metadata.down_revision == "0025"
    assert verification.down_revision == "0024"
    assert governed.down_revision == "0023"


def test_fresh_application_bootstrap_at_head_contains_metadata_tables(
    tmp_path: Path,
) -> None:
    database = tmp_path / "fresh-bootstrap.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    Base.metadata.create_all(engine)
    config = _config(database)
    _run_alembic(command.stamp, config, "head")

    inspector = inspect(engine)
    assert inspector.has_table("metadata_snapshots")
    assert inspector.has_table("metadata_objects")
    assert inspector.has_table("metadata_relationships")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0026"
        )


def _create_deployed_0025_schema(database: Path) -> Config:
    """Model the deployed PostgreSQL schema at 0025 without replaying legacy 0001.

    Revision 0001 calls current ``Base.metadata.create_all`` and is therefore not
    replay-safe with later additive migrations. Existing deployments use the
    resulting schema plus Alembic stamping. This fixture mirrors that established
    bootstrap while removing the not-yet-deployed 0026 tables.
    """
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE metadata_relationships"))
        connection.execute(text("DROP TABLE metadata_objects"))
        connection.execute(text("DROP TABLE metadata_snapshots"))
    config = _config(database)
    _run_alembic(command.stamp, config, "0025")
    return config


def test_deployed_0025_upgrades_without_losing_tenant_or_knowledge_data(
    tmp_path: Path,
) -> None:
    database = tmp_path / "deployed.db"
    config = _create_deployed_0025_schema(database)
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    seeded = {
        "organizations": "org-existing",
        "users": "user-existing",
        "workspaces": "workspace-existing",
        "database_connections": "connection-existing",
        "documents": "document-existing",
        "knowledge_chunks": "knowledge-existing",
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organizations (id,name,slug,is_active,created_at,updated_at) VALUES (:id,'Existing Org','existing-org',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {"id": seeded["organizations"]},
        )
        connection.execute(
            text(
                "INSERT INTO users (id,organization_id,email,full_name,role,is_active,failed_login_count,created_at,updated_at) VALUES (:id,:org,'existing@example.test','Existing','ORG_ADMIN',1,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {"id": seeded["users"], "org": seeded["organizations"]},
        )
        connection.execute(
            text(
                "INSERT INTO workspaces (id,organization_id,name,slug,is_active,created_at,updated_at) VALUES (:id,:org,'Existing Workspace','existing-workspace',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {"id": seeded["workspaces"], "org": seeded["organizations"]},
        )
        connection.execute(
            text(
                "INSERT INTO database_connections (id,organization_id,workspace_id,engine,name,host,database_name,secret_ref,environment_type,max_scan_rows,is_active,created_at,updated_at) VALUES (:id,:org,:ws,'sql_server','Existing Connection','','ExistingDb','env://EXISTING','test',500,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {
                "id": seeded["database_connections"],
                "org": seeded["organizations"],
                "ws": seeded["workspaces"],
            },
        )
        connection.execute(
            text(
                "INSERT INTO documents (id,organization_id,workspace_id,owner_id,title,current_version,is_deleted,created_at,updated_at) VALUES (:id,:org,:ws,:user,'Existing Knowledge',1,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {
                "id": seeded["documents"],
                "org": seeded["organizations"],
                "ws": seeded["workspaces"],
                "user": seeded["users"],
            },
        )
        connection.execute(
            text(
                "INSERT INTO knowledge_chunks (id,organization_id,workspace_id,document_id,source,source_title,chunk_index,content,embedding_json,module_name,table_name,procedure_name,business_object,issue_type,tags,approval_status,created_at,updated_at) VALUES (:id,:org,:ws,:doc,'document','Existing Knowledge',0,'preserve me','[]','','','','','','[]','approved',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {
                "id": seeded["knowledge_chunks"],
                "org": seeded["organizations"],
                "ws": seeded["workspaces"],
                "doc": seeded["documents"],
            },
        )

    _run_alembic(command.upgrade, config, "head")

    with engine.connect() as connection:
        for table, identifier in seeded.items():
            assert (
                connection.execute(
                    text(f"SELECT count(*) FROM {table} WHERE id=:id"), {"id": identifier}
                ).scalar_one()
                == 1
            )
        assert (
            connection.execute(
                text("SELECT content FROM knowledge_chunks WHERE id='knowledge-existing'")
            ).scalar_one()
            == "preserve me"
        )
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0026"
        )
    inspector = inspect(engine)
    assert inspector.has_table("metadata_snapshots")
    assert inspector.has_table("metadata_objects")
    assert inspector.has_table("metadata_relationships")

    _run_alembic(command.downgrade, config, "0025")
    assert not inspect(engine).has_table("metadata_snapshots")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM database_connections WHERE id='connection-existing'")
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM knowledge_chunks WHERE id='knowledge-existing'")
            ).scalar_one()
            == 1
        )
