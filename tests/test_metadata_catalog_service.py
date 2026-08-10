from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    DatabaseConnectionModel,
    MetadataObjectModel,
    MetadataSnapshotModel,
    OrganizationModel,
    WorkspaceModel,
)
from legacydb_copilot.services import metadata_catalog_service as catalog
from legacydb_copilot.services.metadata_search_service import search_metadata


class FakeSqlServerConnector:
    def __init__(
        self,
        *,
        definition="CREATE PROCEDURE dbo.FindOrder AS SELECT * FROM dbo.Orders",
        dependency_rows=None,
        reject_column_dependency_query: bool = False,
    ):
        self.definition = definition
        self.dependency_rows = dependency_rows
        self.reject_column_dependency_query = reject_column_dependency_query
        self.queries: list[str] = []

    def execute_read_only_query(self, sql, limit=1000):
        self.queries.append(sql)
        assert sql.lstrip().upper().startswith("SELECT")
        if "FROM sys.objects o JOIN sys.schemas" in sql and "sys.columns" in sql:
            return [
                {
                    "source_database": "Demo",
                    "object_id": 1,
                    "schema_name": "dbo",
                    "object_name": "Orders",
                    "object_code": "U",
                    "object_type": "USER_TABLE",
                    "column_id": 1,
                    "column_name": "OrderId",
                    "data_type": "int",
                    "max_length": 4,
                    "precision": 10,
                    "scale": 0,
                    "is_nullable": False,
                    "is_identity": True,
                    "is_computed": False,
                    "default_definition": None,
                },
                {
                    "source_database": "Demo",
                    "object_id": 2,
                    "schema_name": "dbo",
                    "object_name": "FindOrder",
                    "object_code": "P ",
                    "object_type": "SQL_STORED_PROCEDURE",
                    "column_id": None,
                    "column_name": None,
                },
            ]
        if "FROM sys.tables t" in sql:
            return [
                {
                    "schema_name": "dbo",
                    "table_name": "Orders",
                    "index_name": "PK_Orders",
                    "is_primary_key": True,
                    "is_unique": True,
                    "has_filter": False,
                    "filter_definition": None,
                    "key_ordinal": 1,
                    "is_included_column": False,
                    "column_name": "OrderId",
                }
            ]
        if "FROM sys.foreign_keys" in sql:
            return []
        if "FROM sys.sql_expression_dependencies" in sql:
            if self.reject_column_dependency_query and "LEFT JOIN sys.columns rc" in sql:
                raise RuntimeError("optional dependency column detail unavailable")
            return self.dependency_rows or [
                {
                    "source_schema": "dbo",
                    "source_name": "FindOrder",
                    "source_type": "P ",
                    "referenced_database_name": None,
                    "referenced_schema_name": "dbo",
                    "referenced_entity_name": "Orders",
                    "referenced_id": 1,
                    "referenced_minor_id": 1,
                    "referenced_column_name": "OrderId",
                    "referenced_class_desc": "OBJECT_OR_COLUMN",
                    "is_schema_bound_reference": False,
                    "is_ambiguous": False,
                    "is_caller_dependent": False,
                }
            ]
        if "FROM sys.objects o" in sql and "sys.sql_modules" in sql:
            return [
                {
                    "schema_name": "dbo",
                    "object_name": "FindOrder",
                    "object_type": "P",
                    "definition": self.definition,
                }
            ]
        raise AssertionError(sql)


@pytest.fixture()
def db_and_connection():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = OrganizationModel(name="Org", slug="org")
        db.add(org)
        db.flush()
        workspace = WorkspaceModel(organization_id=org.id, name="Workspace", slug="workspace")
        db.add(workspace)
        db.flush()
        connection = DatabaseConnectionModel(
            organization_id=org.id,
            workspace_id=workspace.id,
            engine="sql_server",
            name="Demo",
            database_name="Demo",
            secret_ref="env://TEST",
            environment_type="test",
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        yield db, connection


def test_discovery_is_set_based_read_only_and_builds_graph():
    connector = FakeSqlServerConnector()
    found = catalog.discover_sql_server_catalog(connector)
    assert {o.object_type for o in found.objects} == {"TABLE", "PROCEDURE"}
    assert any(r.relationship_type == "READS" for r in found.relationships)
    assert any(r.relationship_type == "INDEX_ON" for r in found.relationships)
    assert len(connector.queries) == 5
    dependency = next(r for r in found.relationships if r.relationship_type == "READS")
    assert dependency.target_column == "OrderId"
    assert dependency.metadata["column_detail_available"] is True


def test_dependency_without_optional_column_name_uses_object_level_relationship():
    connector = FakeSqlServerConnector(
        reject_column_dependency_query=True,
        dependency_rows=[
            {
                "source_schema": "dbo",
                "source_name": "FindOrder",
                "source_type": "P",
                "referenced_database_name": None,
                "referenced_schema_name": "dbo",
                "referenced_entity_name": "Orders",
                "is_ambiguous": False,
                "is_caller_dependent": False,
            }
        ],
    )

    found = catalog.discover_sql_server_catalog(connector)

    dependency = next(r for r in found.relationships if r.relationship_type == "READS")
    assert dependency.target_column == ""
    assert dependency.metadata["column_detail_available"] is False
    assert found.completeness["dependency_columns"] == "unavailable"
    assert all(query.lstrip().upper().startswith("SELECT") for query in connector.queries)


def test_external_dependency_without_local_id_remains_object_level():
    connector = FakeSqlServerConnector(
        dependency_rows=[
            {
                "source_schema": "dbo",
                "source_name": "FindOrder",
                "source_type": "P",
                "referenced_database_name": "ArchiveDb",
                "referenced_schema_name": "history",
                "referenced_entity_name": "Orders",
                "referenced_id": None,
                "referenced_minor_id": 1,
                "referenced_column_name": None,
                "referenced_class_desc": "OBJECT_OR_COLUMN",
                "is_schema_bound_reference": False,
                "is_ambiguous": False,
                "is_caller_dependent": False,
            }
        ]
    )

    found = catalog.discover_sql_server_catalog(connector)

    dependency = next(r for r in found.relationships if r.relationship_type == "READS")
    assert dependency.target_key.startswith("external:archivedb.history.orders")
    assert dependency.target_column == ""
    assert dependency.metadata["external"] is True


def test_local_dependency_with_unresolved_minor_id_remains_object_level():
    connector = FakeSqlServerConnector(
        dependency_rows=[
            {
                "source_schema": "dbo",
                "source_name": "FindOrder",
                "source_type": "P",
                "referenced_database_name": None,
                "referenced_schema_name": "dbo",
                "referenced_entity_name": "Orders",
                "referenced_id": 1,
                "referenced_minor_id": 99,
                "referenced_column_name": None,
                "referenced_class_desc": "OBJECT_OR_COLUMN",
                "is_schema_bound_reference": False,
                "is_ambiguous": False,
                "is_caller_dependent": False,
            }
        ]
    )

    found = catalog.discover_sql_server_catalog(connector)

    dependency = next(r for r in found.relationships if r.relationship_type == "READS")
    assert dependency.target_key == "object:dbo.orders"
    assert dependency.target_column == ""
    assert dependency.metadata["column_detail_available"] is False


def test_dynamic_sql_dependency_is_uncertain_even_when_catalog_row_exists():
    connector = FakeSqlServerConnector(
        definition="CREATE PROCEDURE dbo.FindOrder AS EXEC(@sql)"
    )

    found = catalog.discover_sql_server_catalog(connector)

    dependency = next(r for r in found.relationships if r.relationship_type == "READS")
    assert dependency.metadata["uncertain"] is True


def test_stable_fingerprint_and_definition_change():
    first = catalog.discover_sql_server_catalog(FakeSqlServerConnector())
    same = catalog.discover_sql_server_catalog(FakeSqlServerConnector())
    changed = catalog.discover_sql_server_catalog(
        FakeSqlServerConnector(
            definition="ALTER PROCEDURE dbo.FindOrder AS SELECT OrderId FROM dbo.Orders"
        )
    )
    assert catalog.catalog_fingerprint(first) == catalog.catalog_fingerprint(same)
    assert catalog.catalog_fingerprint(first) != catalog.catalog_fingerprint(changed)


def test_refresh_activates_complete_snapshot_and_reuses_it(db_and_connection):
    db, connection = db_and_connection
    snapshot = catalog.refresh_metadata(
        db, connection=connection, connector=FakeSqlServerConnector()
    )
    assert snapshot.status == "READY" and snapshot.is_active
    assert snapshot.discovery_version == "2"
    assert catalog.snapshot_summary(snapshot)["counts"]["result_set_lineages"] == 1
    assert db.query(MetadataObjectModel).filter_by(snapshot_id=snapshot.id).count() == 2
    cached = catalog.schema_metadata_from_catalog(db, snapshot)
    assert cached.tables == ["dbo.Orders"]
    assert cached.cache_diagnostics["cache_source"] == "persistent_metadata_catalog"
    assert cached.cache_diagnostics["connection_id"] == connection.id
    assert cached.cache_diagnostics["metadata_snapshot_id"] == snapshot.id
    assert cached.cache_diagnostics["metadata_snapshot_version"] == snapshot.version
    assert cached.cache_diagnostics["metadata_fingerprint"] == snapshot.schema_hash
    assert "dbo.FindOrder" in cached.result_set_lineages
    assert cached.result_set_lineages["dbo.FindOrder"]["base_object"] == "dbo.Orders"
    persisted_procedure = db.query(MetadataObjectModel).filter_by(
        snapshot_id=snapshot.id, object_type="PROCEDURE"
    ).one()
    assert '"result_set_lineage"' in persisted_procedure.metadata_json
    assert not any(
        sensitive in str(cached.cache_diagnostics).lower()
        for sensitive in ("password", "connection_string", "env://test")
    )

    class NoLiveMetadata:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected live metadata call: {name}")

    result = search_metadata(
        NoLiveMetadata(),
        "Find an order by OrderId",
        EntityExtractionResult([], None, None, business_keywords=["order"]),
        schema_metadata=cached,
    )
    assert result.tables[0].name == "dbo.Orders"
    assert result.tables[0].relationship_metadata_status == "catalog"


def test_unchanged_refresh_versions_snapshot_without_structural_rebuild(db_and_connection):
    db, connection = db_and_connection
    first = catalog.refresh_metadata(db, connection=connection, connector=FakeSqlServerConnector())
    second = catalog.refresh_metadata(db, connection=connection, connector=FakeSqlServerConnector())
    assert second.version == first.version + 1
    assert second.schema_hash == first.schema_hash
    assert catalog.snapshot_summary(second)["changes"]["structural_change"] is False
    assert db.get(MetadataSnapshotModel, first.id).is_active is False


def test_failed_refresh_preserves_previous_active_snapshot(db_and_connection):
    db, connection = db_and_connection
    first = catalog.refresh_metadata(db, connection=connection, connector=FakeSqlServerConnector())

    class Broken:
        def execute_read_only_query(self, *_args, **_kwargs):
            raise PermissionError("metadata denied")

    with pytest.raises(PermissionError):
        catalog.refresh_metadata(db, connection=connection, connector=Broken())
    assert (
        catalog.active_snapshot(
            db,
            organization_id=connection.organization_id,
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
        ).id
        == first.id
    )
    assert (
        db.query(MetadataSnapshotModel)
        .filter_by(connection_id=connection.id, status="FAILED")
        .count()
        == 1
    )


def test_tenant_scope_prevents_cross_workspace_lookup(db_and_connection):
    db, connection = db_and_connection
    catalog.refresh_metadata(db, connection=connection, connector=FakeSqlServerConnector())
    assert (
        catalog.active_snapshot(
            db,
            organization_id=connection.organization_id,
            workspace_id="another-workspace",
            connection_id=connection.id,
        )
        is None
    )


def test_same_database_name_remains_isolated_by_connection(db_and_connection):
    db, connection_a = db_and_connection
    connection_b = DatabaseConnectionModel(
        organization_id=connection_a.organization_id,
        workspace_id=connection_a.workspace_id,
        engine="sql_server",
        name="Second Connection",
        database_name=connection_a.database_name,
        secret_ref="env://SECOND_TEST",
        environment_type="test",
    )
    db.add(connection_b)
    db.commit()
    first = catalog.refresh_metadata(
        db, connection=connection_a, connector=FakeSqlServerConnector()
    )
    second = catalog.refresh_metadata(
        db,
        connection=connection_b,
        connector=FakeSqlServerConnector(
            definition="CREATE PROCEDURE dbo.FindOrder AS SELECT 2"
        ),
    )
    assert first.connection_id == connection_a.id
    assert second.connection_id == connection_b.id
    assert first.schema_hash != second.schema_hash
    assert db.get(MetadataSnapshotModel, first.id).is_active is True
    assert db.get(MetadataSnapshotModel, second.id).is_active is True


def test_same_display_and_workspace_names_across_tenants_do_not_leak(
    db_and_connection,
):
    db, connection_a = db_and_connection
    other_org = OrganizationModel(name="Other Org", slug="other-org")
    db.add(other_org)
    db.flush()
    other_workspace = WorkspaceModel(
        organization_id=other_org.id, name="Workspace", slug="workspace"
    )
    db.add(other_workspace)
    db.flush()
    connection_b = DatabaseConnectionModel(
        organization_id=other_org.id,
        workspace_id=other_workspace.id,
        engine="sql_server",
        name=connection_a.name,
        database_name=connection_a.database_name,
        secret_ref="env://OTHER_TENANT_TEST",
        environment_type="test",
    )
    db.add(connection_b)
    db.commit()
    snapshot_b = catalog.refresh_metadata(
        db, connection=connection_b, connector=FakeSqlServerConnector()
    )
    assert (
        catalog.active_snapshot(
            db,
            organization_id=connection_a.organization_id,
            workspace_id=connection_a.workspace_id,
            connection_id=connection_b.id,
        )
        is None
    )
    assert snapshot_b.organization_id == other_org.id
    assert snapshot_b.workspace_id == other_workspace.id


def test_multiple_active_snapshots_fail_closed(db_and_connection):
    db, connection = db_and_connection
    for version in (1, 2):
        db.add(
            MetadataSnapshotModel(
                organization_id=connection.organization_id,
                workspace_id=connection.workspace_id,
                connection_id=connection.id,
                version=version,
                status="READY",
                is_active=True,
            )
        )
    db.commit()
    with pytest.raises(RuntimeError, match="multiple active snapshots"):
        catalog.active_snapshot(
            db,
            organization_id=connection.organization_id,
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
        )


def test_catalog_models_do_not_contain_credentials():
    forbidden = {"connection_string", "password", "secret", "token", "credential"}
    for model in (MetadataSnapshotModel, MetadataObjectModel):
        columns = {column.name.lower() for column in model.__table__.columns}
        assert not any(term in column for column in columns for term in forbidden)


def test_concurrent_refresh_returns_active_snapshot(db_and_connection, monkeypatch):
    db, connection = db_and_connection
    first = catalog.refresh_metadata(db, connection=connection, connector=FakeSqlServerConnector())
    lock = catalog._lock_for(connection.id)
    lock.acquire()
    try:
        assert (
            catalog.refresh_metadata(
                db, connection=connection, connector=FakeSqlServerConnector()
            ).id
            == first.id
        )
    finally:
        lock.release()
