from __future__ import annotations

from contextlib import nullcontext

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
