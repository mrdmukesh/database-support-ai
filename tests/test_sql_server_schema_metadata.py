from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import Mock

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.db.adapters import SQLServerAdapter
from legacydb_copilot.db.connector import DatabaseConnector, SchemaMetadata
from legacydb_copilot.services.metadata_search_service import (
    resolve_qualified_object_names,
    search_metadata,
)


class _Inspector:
    def __init__(self):
        self.schemas = ["sys", "INFORMATION_SCHEMA", "dbo", "eval"]
        self.tables = {
            "dbo": ["shipments", "legacy_only"],
            "eval": ["shipments", "transport_work_orders", "exceptions"],
        }
        self.views = {"dbo": [], "eval": ["vw_shipping_operations_1"]}

    def get_schema_names(self):
        return self.schemas

    def get_table_names(self, schema=None):
        return self.tables.get(schema, [])

    def get_view_names(self, schema=None):
        return self.views.get(schema, [])

    def get_columns(self, name, schema=None):
        return [{"name": "ShipmentsId", "type": "BIGINT", "nullable": False, "default": None}]

    def get_pk_constraint(self, name, schema=None):
        return {"constrained_columns": ["ShipmentsId"]}

    def get_foreign_keys(self, name, schema=None):
        if schema == "eval" and name == "transport_work_orders":
            return [{
                "name": "FK_work_orders_shipments",
                "constrained_columns": ["ShipmentsId"],
                "referred_schema": "eval",
                "referred_table": "shipments",
                "referred_columns": ["ShipmentsId"],
            }]
        return []

    def get_indexes(self, name, schema=None):
        return [{"name": f"IX_{schema}_{name}", "column_names": ["ShipmentsId"], "unique": False}]


class _Result:
    def fetchall(self):
        return [
            ("eval", "fn_shipping_active_status"),
            ("eval", "tr_bookings_audit"),
            ("eval", "usp_shipping_workflow_1"),
        ]


class _Connection:
    def execute(self, statement):
        return _Result()


class _Engine:
    def connect(self):
        return nullcontext(_Connection())


def _adapter(monkeypatch) -> SQLServerAdapter:
    inspector = _Inspector()
    monkeypatch.setattr("legacydb_copilot.db.adapters.inspect", lambda engine: inspector)
    return SQLServerAdapter(_Engine())


def test_sql_server_discovers_dbo_and_non_default_schemas_without_system_schemas(monkeypatch):
    adapter = _adapter(monkeypatch)

    assert adapter.list_tables() == [
        "dbo.legacy_only",
        "dbo.shipments",
        "eval.exceptions",
        "eval.shipments",
        "eval.transport_work_orders",
    ]
    assert adapter.list_views() == ["eval.vw_shipping_operations_1"]
    assert all(
        not name.lower().startswith(("sys.", "information_schema."))
        for name in adapter.list_tables()
    )


def test_sql_server_schema_qualified_reflection(monkeypatch):
    adapter = _adapter(monkeypatch)

    assert adapter.list_columns("eval.shipments")[0]["name"] == "ShipmentsId"
    assert adapter.get_primary_key("eval.shipments")["constrained_columns"] == ["ShipmentsId"]
    foreign_key = adapter.list_foreign_keys("eval.transport_work_orders")[0]
    assert foreign_key["referred_table"] == "eval.shipments"
    assert adapter.list_indexes("eval.shipments")[0]["name"] == "IX_eval_shipments"


def test_sql_server_discovers_schema_qualified_programmable_objects(monkeypatch):
    adapter = _adapter(monkeypatch)

    assert adapter.list_procedures() == [
        "eval.fn_shipping_active_status",
        "eval.tr_bookings_audit",
        "eval.usp_shipping_workflow_1",
    ]


def test_unique_leaf_names_resolve_but_duplicate_names_remain_ambiguous():
    objects = ["dbo.shipments", "eval.shipments", "eval.exceptions"]

    assert resolve_qualified_object_names(objects, {"exceptions"}) == {
        "exceptions": "eval.exceptions"
    }
    assert resolve_qualified_object_names(objects, {"eval.shipments"}) == {
        "eval.shipments": "eval.shipments"
    }
    assert resolve_qualified_object_names(objects, {"shipments"}) == {}


def test_connector_and_existing_metadata_consumers_keep_qualified_names(monkeypatch):
    adapter = _adapter(monkeypatch)
    connector = DatabaseConnector(DatabaseEngine.SQL_SERVER, "unused")
    connector._engine = adapter.engine
    connector._adapter = adapter

    schema = connector.get_table_schema("eval.transport_work_orders")
    assert schema["table_name"] == "eval.transport_work_orders"
    assert schema["foreign_keys"][0]["referred_table"] == "eval.shipments"

    metadata = SchemaMetadata(
        "sql_server",
        adapter.list_tables(),
        adapter.list_views(),
        adapter.list_procedures(),
        "test",
    )
    result = search_metadata(
        connector,
        "Inspect table: eval.transport_work_orders",
        extract_entities("Inspect table: eval.transport_work_orders"),
        schema_metadata=metadata,
    )
    assert result.tables[0].name == "eval.transport_work_orders"
    assert result.tables[0].foreign_keys[0]["referred_table"] == "eval.shipments"
    assert result.views == ["eval.vw_shipping_operations_1"]


def test_table_schema_reuses_cached_object_inventory(monkeypatch):
    adapter = _adapter(monkeypatch)
    connector = DatabaseConnector(DatabaseEngine.SQL_SERVER, "unused")
    connector._engine = adapter.engine
    connector._adapter = adapter
    connector._schema_metadata_cache = SchemaMetadata(
        "sql_server",
        ["eval.transport_work_orders"],
        [],
        [],
        "test",
    )
    connector._schema_metadata_cached_at = 1.0

    def unexpected_inventory_refresh():
        raise AssertionError("cached table inventory must not be re-enumerated")

    monkeypatch.setattr(adapter, "list_tables", unexpected_inventory_refresh)

    schema = connector.get_table_schema("eval.transport_work_orders")

    assert schema["table_name"] == "eval.transport_work_orders"


def test_lightweight_columns_do_not_reflect_keys_or_indexes(monkeypatch):
    adapter = _adapter(monkeypatch)
    connector = DatabaseConnector(DatabaseEngine.SQL_SERVER, "unused")
    connector._engine = adapter.engine
    connector._adapter = adapter

    monkeypatch.setattr(
        adapter,
        "list_foreign_keys",
        lambda name: (_ for _ in ()).throw(AssertionError("foreign keys reflected")),
    )
    monkeypatch.setattr(
        adapter,
        "list_indexes",
        lambda name: (_ for _ in ()).throw(AssertionError("indexes reflected")),
    )

    columns = connector.get_table_columns("eval.transport_work_orders")

    assert [column["name"] for column in columns] == ["ShipmentsId"]

    search_schema = connector.get_table_search_schema(
        "eval.transport_work_orders"
    )
    assert search_schema["foreign_keys"] == []
    assert search_schema["indexes"] == []
    assert search_schema["enrichment_loaded"] is False
    assert search_schema["relationship_metadata_status"] == "not_loaded"


def test_sql_server_candidate_search_skips_relationship_enrichment(monkeypatch):
    adapter = _adapter(monkeypatch)
    connector = DatabaseConnector(DatabaseEngine.SQL_SERVER, "unused")
    connector._engine = adapter.engine
    connector._adapter = adapter
    foreign_key_calls = []
    index_calls = []
    monkeypatch.setattr(
        adapter,
        "list_foreign_keys",
        lambda name: foreign_key_calls.append(name),
    )
    monkeypatch.setattr(
        adapter,
        "list_indexes",
        lambda name: index_calls.append(name),
    )
    metadata = SchemaMetadata(
        "sql_server",
        adapter.list_tables(),
        adapter.list_views(),
        adapter.list_procedures(),
        "test",
    )

    result = search_metadata(
        connector,
        "Investigate transport work order processing",
        extract_entities("Investigate transport work order processing"),
        schema_metadata=metadata,
    )

    selected = next(
        table
        for table in result.tables
        if table.name == "eval.transport_work_orders"
    )
    assert selected.column_types == {"ShipmentsId": "BIGINT"}
    assert selected.enrichment_loaded is False
    assert selected.relationship_metadata_status == "not_loaded"
    assert foreign_key_calls == []
    assert index_calls == []
    trace = next(
        item
        for item in result.candidate_trace
        if item["name"] == "eval.transport_work_orders"
    )
    assert trace["relationship_metadata_status"] == "not_loaded"


def test_non_sql_server_search_schema_keeps_detailed_reflection(monkeypatch):
    connector = DatabaseConnector(DatabaseEngine.POSTGRESQL, "unused")
    detailed = {
        "table_name": "public.orders",
        "columns": [{"name": "id", "type": "INTEGER"}],
        "primary_key": ["id"],
        "foreign_keys": [{"name": "fk_customer"}],
        "indexes": [{"name": "ix_orders"}],
    }
    monkeypatch.setattr(connector, "get_table_schema", lambda name: detailed)

    assert connector.get_table_search_schema("public.orders") is detailed


def test_sql_server_connections_receive_a_bounded_query_timeout(monkeypatch):
    dbapi_connection = Mock()
    engine = Mock()
    engine.connect.return_value = nullcontext(
        Mock(execute=Mock(return_value=Mock()))
    )
    listener = {}

    engine_options = {}

    def create_test_engine(*args, **kwargs):
        engine_options.update(kwargs)
        return engine

    monkeypatch.setattr(
        "legacydb_copilot.db.connector.create_engine",
        create_test_engine,
    )
    monkeypatch.setattr(
        "legacydb_copilot.db.connector.event.listens_for",
        lambda target, name: lambda callback: listener.setdefault(name, callback),
    )
    monkeypatch.setattr(
        "legacydb_copilot.db.connector.adapter_for",
        lambda database_engine, created_engine: Mock(),
    )

    connector = DatabaseConnector(DatabaseEngine.SQL_SERVER, "unused")
    connector.connect()
    listener["connect"](dbapi_connection, Mock())

    assert dbapi_connection.timeout == 30
    assert engine_options["pool_pre_ping"] is False
    assert engine_options["pool_recycle"] == 60
