from __future__ import annotations

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.agents.investigation_planner_agent import build_investigation_plan
from legacydb_copilot.db.connector import ConnectionPool, DatabaseConnector
from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.routers.chat import _investigation_status
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata


QUESTION = "Delivery is complete for shipment SHP-5001; why is the empty-return work order missing?"


def metadata() -> MetadataSearchResult:
    parent = TableMetadata("shipments", ["ShipmentsId", "BusinessKey", "Status"], 12, ["ShipmentsId"], [], [])
    child = TableMetadata("transport_work_orders", ["TransportWorkOrdersId", "ShipmentsId", "BusinessKey", "Status", "Details"], 14, ["TransportWorkOrdersId"], [], [])
    exception = TableMetadata("exceptions", ["ExceptionsId", "BusinessKey", "Status", "CorrelationId", "Details"], 2, ["ExceptionsId"], [], [])
    return MetadataSearchResult([child, parent, exception], [], [], "8.0", engine_type="mysql")


def test_multiword_missing_child_uses_pascal_case_relationship_columns():
    plan = build_investigation_plan(InvestigationIntent.MISSING_DATA, metadata(), extract_entities(QUESTION))
    sql = "\n".join(item.sql for item in plan)
    assert "LEFT JOIN transport_work_orders" in sql
    assert "c.ShipmentsId = p.ShipmentsId" in sql
    assert "MISSING_RELATED_RECORD" in sql


def test_generic_correlation_id_is_not_inferred_as_parent_child_foreign_key():
    parent = TableMetadata("empty_return_instructions", ["EmptyReturnInstructionsId", "BusinessKey", "CorrelationId"], 13, ["EmptyReturnInstructionsId"], [], [])
    child = TableMetadata("transport_work_orders", ["TransportWorkOrdersId", "ShipmentsId", "BusinessKey", "CorrelationId"], 14, ["TransportWorkOrdersId"], [], [])
    shipment = TableMetadata("shipments", ["ShipmentsId", "BusinessKey", "Status", "CorrelationId"], 12, ["ShipmentsId"], [], [])
    md = MetadataSearchResult([child, parent, shipment], [], [], "8", engine_type="mysql")
    sql = "\n".join(item.sql for item in build_investigation_plan(InvestigationIntent.MISSING_DATA, md, extract_entities(QUESTION)))
    assert "c.ShipmentsId = p.ShipmentsId" in sql
    assert "c.CorrelationId = p.CorrelationId" not in sql


def test_shared_non_primary_parent_column_does_not_create_sibling_relationship():
    milestone = TableMetadata("shipment_milestones", ["ShipmentMilestonesId", "ShipmentsId", "BusinessKey"], 20, ["ShipmentMilestonesId"], [], [])
    shipment = TableMetadata("shipments", ["ShipmentsId", "BusinessKey", "Status"], 10, ["ShipmentsId"], [], [])
    child = TableMetadata("transport_work_orders", ["TransportWorkOrdersId", "ShipmentsId", "BusinessKey", "Details"], 14, ["TransportWorkOrdersId"], [], [])
    md = MetadataSearchResult([milestone, child, shipment], [], [], "8", engine_type="mysql")
    sql = "\n".join(item.sql for item in build_investigation_plan(InvestigationIntent.MISSING_DATA, md, extract_entities(QUESTION)))
    assert "FROM shipments p" in sql
    assert "FROM shipment_milestones p" not in sql


def test_declared_foreign_key_overrides_higher_scored_inferred_parent():
    declared_fk = [{"columns":["ShipmentsId"],"referred_table":"shipments","referred_columns":["ShipmentsId"]}]
    child = TableMetadata("transport_work_orders", ["TransportWorkOrdersId","ShipmentsId","BusinessKey","Details"], 14, ["TransportWorkOrdersId"], declared_fk, [])
    wrong = TableMetadata("shipment_milestones", ["ShipmentMilestonesId","ShipmentsId","BusinessKey"], 99, ["ShipmentMilestonesId"], [], [])
    parent = TableMetadata("shipments", ["ShipmentsId","BusinessKey","Status"], 1, ["ShipmentsId"], [], [])
    md = MetadataSearchResult([wrong,child,parent],[],[],"16",engine_type="sql_server")
    sql = "\n".join(item.sql for item in build_investigation_plan(InvestigationIntent.MISSING_DATA, md, extract_entities(QUESTION)))
    assert "FROM shipments p" in sql
    assert "c.ShipmentsId = p.ShipmentsId" in sql


def test_zero_child_rows_are_represented_by_negative_existence_row():
    evidence = [EvidenceResult("Confirmed Missing Related Record Candidates", "SELECT ... FROM shipments p LEFT JOIN transport_work_orders c ON c.ShipmentsId=p.ShipmentsId", [{"parent_reference": "SHP-5001", "parent_status": "Delivered", "child_reference": None, "issue_type": "MISSING_RELATED_RECORD"}])]
    gate = run_evidence_gate(question=QUESTION, intent=InvestigationIntent.MISSING_DATA, entities=extract_entities(QUESTION), metadata=metadata(), evidence=evidence, evidence_focus=None, documents=[])
    assert gate.reproduced is True
    assert gate.business_key_exists is True
    assert gate.reported_condition_exists is True


def test_connector_cache_key_is_engine_specific_and_secret_free():
    pool = ConnectionPool()
    mysql = pool.connector_cache_key(DatabaseEngine.MYSQL, "mysql+pymysql://user:secret@localhost:3306/db")
    sqlserver = pool.connector_cache_key(DatabaseEngine.SQL_SERVER, "mssql+pyodbc://user:secret@localhost:1433/db")
    assert mysql != sqlserver
    assert "secret" not in mysql
    assert len(mysql) == 64


def test_forced_refresh_replaces_cached_metadata(monkeypatch):
    connector = DatabaseConnector(DatabaseEngine.MYSQL, "mysql://unused")
    state = {"tables": ["old_table"]}

    class Adapter:
        def list_tables(self): return list(state["tables"])
        def list_views(self): return []
        def get_version(self): return "8"

    monkeypatch.setattr(connector, "get_adapter", lambda: Adapter())
    monkeypatch.setattr(connector, "list_procedures", lambda: [])
    assert connector.get_schema_metadata().tables == ["old_table"]
    state["tables"] = ["new_table"]
    assert connector.get_schema_metadata().tables == ["old_table"]
    refreshed = connector.get_schema_metadata(force_refresh=True)
    assert refreshed.tables == ["new_table"]
    assert refreshed.cache_diagnostics["refresh_reason"] == "forced_refresh"


def test_ai_skip_provenance_never_maps_to_ai_answered():
    assert _investigation_status("MISSING_DATA", "AI_SKIPPED_BY_EVIDENCE_GATE") == "AI_SKIPPED_BY_EVIDENCE_GATE"
    assert _investigation_status("MISSING_DATA", "AI_INVOCATION_FAILED") == "AI_INVOCATION_FAILED"
