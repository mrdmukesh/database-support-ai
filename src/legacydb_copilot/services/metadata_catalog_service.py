from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from legacydb_copilot.db.connector import SchemaMetadata
from legacydb_copilot.db.models import (
    MetadataObjectModel,
    MetadataRelationshipModel,
    MetadataSnapshotModel,
)

DISCOVERY_VERSION = "1"
_locks_guard = threading.Lock()
_connection_locks: dict[str, threading.Lock] = {}


@dataclass(frozen=True)
class CatalogObject:
    object_type: str
    schema_name: str
    object_name: str
    source_object_id: str = ""
    definition: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.object_type}:{self.schema_name}.{self.object_name}".lower()


@dataclass(frozen=True)
class CatalogRelationship:
    source_key: str
    target_key: str
    relationship_type: str
    source_column: str = ""
    target_column: str = ""
    dependency_distance: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveredCatalog:
    source_database: str
    objects: list[CatalogObject]
    relationships: list[CatalogRelationship]
    completeness: dict[str, str] = field(default_factory=dict)


def _lock_for(connection_id: str) -> threading.Lock:
    with _locks_guard:
        return _connection_locks.setdefault(connection_id, threading.Lock())


def _canonical_definition(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def definition_hash(value: str | None) -> str:
    normalized = _canonical_definition(value)
    return hashlib.sha256(normalized.encode()).hexdigest() if normalized else ""


def catalog_fingerprint(catalog: DiscoveredCatalog) -> str:
    payload = {
        "objects": sorted(
            (
                {
                    "key": o.key,
                    "definition_hash": definition_hash(o.definition),
                    "metadata": o.metadata,
                }
                for o in catalog.objects
            ),
            key=lambda item: item["key"],
        ),
        "relationships": sorted(
            (
                {
                    "source": r.source_key.lower(),
                    "target": r.target_key.lower(),
                    "type": r.relationship_type,
                    "source_column": r.source_column,
                    "target_column": r.target_column,
                    "metadata": r.metadata,
                }
                for r in catalog.relationships
            ),
            key=lambda item: (
                item["source"],
                item["target"],
                item["type"],
                item["source_column"],
                item["target_column"],
            ),
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _qname(schema: Any, name: Any) -> str:
    return f"{schema}.{name}" if schema else str(name)


def discover_sql_server_catalog(connector) -> DiscoveredCatalog:
    """Read SQL Server structure in bounded, set-based SELECTs; never execute user modules."""
    object_rows = connector.execute_read_only_query(
        """
SELECT DB_NAME() source_database, o.object_id, s.name schema_name, o.name object_name,
       o.type object_code, o.type_desc object_type, c.column_id, c.name column_name,
       ty.name data_type, c.max_length, c.precision, c.scale, c.is_nullable,
       c.is_identity, c.is_computed, dc.definition default_definition
FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id
LEFT JOIN sys.columns c ON c.object_id=o.object_id LEFT JOIN sys.types ty ON ty.user_type_id=c.user_type_id
LEFT JOIN sys.default_constraints dc ON dc.object_id=c.default_object_id
WHERE o.is_ms_shipped=0 AND o.type IN ('U','V','P','FN','IF','TF','TR','SN','SO')
ORDER BY o.object_id,c.column_id""",
        limit=100000,
    )
    index_rows = connector.execute_read_only_query(
        """
SELECT s.name schema_name,t.name table_name,i.name index_name,i.is_primary_key,i.is_unique,
       i.has_filter,i.filter_definition,ic.key_ordinal,ic.is_included_column,c.name column_name
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.indexes i ON i.object_id=t.object_id
JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
WHERE t.is_ms_shipped=0 AND i.name IS NOT NULL ORDER BY t.object_id,i.index_id,ic.key_ordinal,ic.index_column_id""",
        limit=100000,
    )
    fk_rows = connector.execute_read_only_query(
        """
SELECT ss.name source_schema,st.name source_table,sc.name source_column, fk.name constraint_name,
       ts.name target_schema,tt.name target_table,tc.name target_column,fk.delete_referential_action_desc,fk.update_referential_action_desc
FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id
JOIN sys.tables st ON st.object_id=fkc.parent_object_id JOIN sys.schemas ss ON ss.schema_id=st.schema_id JOIN sys.columns sc ON sc.object_id=st.object_id AND sc.column_id=fkc.parent_column_id
JOIN sys.tables tt ON tt.object_id=fkc.referenced_object_id JOIN sys.schemas ts ON ts.schema_id=tt.schema_id JOIN sys.columns tc ON tc.object_id=tt.object_id AND tc.column_id=fkc.referenced_column_id""",
        limit=100000,
    )
    dependency_rows = connector.execute_read_only_query(
        """
SELECT ss.name source_schema,so.name source_name,so.type source_type,
       d.referenced_database_name,d.referenced_schema_name,d.referenced_entity_name,d.referenced_minor_name,
       d.is_ambiguous,d.is_caller_dependent
FROM sys.sql_expression_dependencies d JOIN sys.objects so ON so.object_id=d.referencing_id JOIN sys.schemas ss ON ss.schema_id=so.schema_id
WHERE so.is_ms_shipped=0""",
        limit=100000,
    )
    completeness = {
        "objects": "complete",
        "columns": "complete",
        "indexes": "complete",
        "foreign_keys": "complete",
        "definitions": "complete",
        "dependencies": "complete",
    }
    try:
        module_rows = connector.execute_read_only_query(
            """
SELECT s.name schema_name,o.name object_name,o.type object_type,m.definition
FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id LEFT JOIN sys.sql_modules m ON m.object_id=o.object_id
WHERE o.is_ms_shipped=0 AND o.type IN ('V','P','FN','IF','TF','TR')""",
            limit=50000,
        )
    except Exception:
        module_rows = []
        completeness["definitions"] = "partial"

    code_map = {
        "U": "TABLE",
        "V": "VIEW",
        "P": "PROCEDURE",
        "FN": "FUNCTION",
        "IF": "FUNCTION",
        "TF": "FUNCTION",
        "TR": "TRIGGER",
        "SN": "SYNONYM",
        "SO": "SEQUENCE",
    }
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    source_database = ""
    for row in object_rows:
        source_database = source_database or str(row.get("source_database") or "")
        typ = code_map.get(str(row.get("object_code")), str(row.get("object_type") or "OBJECT"))
        key = (typ, str(row.get("schema_name") or ""), str(row.get("object_name") or ""))
        item = grouped.setdefault(
            key, {"source_object_id": str(row.get("object_id") or ""), "columns": []}
        )
        if row.get("column_name"):
            item["columns"].append(
                {
                    k: row.get(k)
                    for k in (
                        "column_name",
                        "data_type",
                        "max_length",
                        "precision",
                        "scale",
                        "is_nullable",
                        "is_identity",
                        "is_computed",
                        "default_definition",
                    )
                }
            )
    definitions = {
        (str(r.get("schema_name") or ""), str(r.get("object_name") or "")): r.get("definition")
        for r in module_rows
    }
    objects = [
        CatalogObject(
            t,
            s,
            n,
            v["source_object_id"],
            definitions.get((s, n)),
            {
                "columns": v["columns"],
                "definition_available": (s, n) in definitions and definitions[(s, n)] is not None,
                "dynamic_sql": bool(
                    re.search(
                        r"\b(?:sp_executesql|EXEC\s*\()", str(definitions.get((s, n)) or ""), re.I
                    )
                ),
            },
        )
        for (t, s, n), v in grouped.items()
    ]
    relationships: list[CatalogRelationship] = []
    for row in index_rows:
        table_key = f"table:{_qname(row.get('schema_name'), row.get('table_name'))}".lower()
        index_key = f"index:{_qname(row.get('schema_name'), row.get('index_name'))}".lower()
        relationships.append(
            CatalogRelationship(
                index_key,
                table_key,
                "INDEX_ON",
                source_column=str(row.get("column_name") or ""),
                metadata={
                    k: row.get(k)
                    for k in (
                        "is_primary_key",
                        "is_unique",
                        "has_filter",
                        "filter_definition",
                        "is_included_column",
                        "key_ordinal",
                    )
                },
            )
        )
    for row in fk_rows:
        relationships.append(
            CatalogRelationship(
                f"table:{_qname(row.get('source_schema'), row.get('source_table'))}".lower(),
                f"table:{_qname(row.get('target_schema'), row.get('target_table'))}".lower(),
                "FOREIGN_KEY",
                str(row.get("source_column") or ""),
                str(row.get("target_column") or ""),
                metadata={"name": row.get("constraint_name"), "source": "FOREIGN_KEY"},
            )
        )
    type_prefix = {
        "P": "procedure",
        "V": "view",
        "FN": "function",
        "IF": "function",
        "TF": "function",
        "TR": "trigger",
    }
    for row in dependency_rows:
        source_type = type_prefix.get(str(row.get("source_type")), "object")
        source = f"{source_type}:{_qname(row.get('source_schema'), row.get('source_name'))}".lower()
        external = bool(row.get("referenced_database_name"))
        target_name = _qname(row.get("referenced_schema_name"), row.get("referenced_entity_name"))
        target = (
            f"external:{row.get('referenced_database_name')}.{target_name}".lower()
            if external
            else f"object:{target_name}".lower()
        )
        definition = str(
            definitions.get(
                (str(row.get("source_schema") or ""), str(row.get("source_name") or ""))
            )
            or ""
        )
        rel_type = "REFERENCES"
        if source_type == "procedure" and re.search(
            rf"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO)\s+[^;]*{re.escape(str(row.get('referenced_entity_name') or ''))}\b",
            definition,
            re.I,
        ):
            rel_type = "WRITES"
        elif source_type == "procedure":
            rel_type = "READS"
        elif source_type == "view":
            rel_type = "VIEW_DEPENDS_ON"
        elif source_type == "function":
            rel_type = "FUNCTION_DEPENDS_ON"
        relationships.append(
            CatalogRelationship(
                source,
                target,
                rel_type,
                target_column=str(row.get("referenced_minor_name") or ""),
                metadata={
                    "source": "SQL_EXPRESSION_DEPENDENCY",
                    "external": external,
                    "uncertain": bool(row.get("is_ambiguous") or row.get("is_caller_dependent")),
                },
            )
        )
    return DiscoveredCatalog(source_database, objects, relationships, completeness)


def active_snapshot(
    db: Session, *, organization_id: str, workspace_id: str, connection_id: str
) -> MetadataSnapshotModel | None:
    return (
        db.query(MetadataSnapshotModel)
        .filter_by(
            organization_id=organization_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
            is_active=True,
            status="READY",
        )
        .first()
    )


def refresh_metadata(db: Session, *, connection, connector) -> MetadataSnapshotModel:
    lock = _lock_for(connection.id)
    if not lock.acquire(blocking=False):
        current = active_snapshot(
            db,
            organization_id=connection.organization_id,
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
        )
        if current:
            return current
        raise RuntimeError("Metadata refresh is already in progress")
    previous = active_snapshot(
        db,
        organization_id=connection.organization_id,
        workspace_id=connection.workspace_id,
        connection_id=connection.id,
    )
    version = (
        int(
            db.query(func.max(MetadataSnapshotModel.version))
            .filter_by(connection_id=connection.id)
            .scalar()
            or 0
        )
        + 1
    )
    candidate = MetadataSnapshotModel(
        organization_id=connection.organization_id,
        workspace_id=connection.workspace_id,
        connection_id=connection.id,
        version=version,
        status="DISCOVERING",
        source_database=connection.database_name,
    )
    db.add(candidate)
    db.commit()
    try:
        if connection.engine != "sql_server":
            raise ValueError(
                "Persistent metadata discovery currently supports SQL Server connections"
            )
        catalog = discover_sql_server_catalog(connector)
        fingerprint = catalog_fingerprint(catalog)
        previous_keys: set[str] = set()
        if previous:
            previous_keys = {
                f"{o.object_type}:{o.schema_name}.{o.object_name}".lower()
                for o in db.query(MetadataObjectModel).filter_by(snapshot_id=previous.id)
            }
        current_keys = {o.key for o in catalog.objects}
        for obj in catalog.objects:
            db.add(
                MetadataObjectModel(
                    snapshot_id=candidate.id,
                    object_type=obj.object_type,
                    schema_name=obj.schema_name,
                    object_name=obj.object_name,
                    source_object_id=obj.source_object_id,
                    definition_hash=definition_hash(obj.definition),
                    definition=obj.definition,
                    metadata_json=json.dumps(obj.metadata, default=str),
                )
            )
        for rel in catalog.relationships:
            db.add(
                MetadataRelationshipModel(
                    snapshot_id=candidate.id,
                    source_key=rel.source_key,
                    target_key=rel.target_key,
                    relationship_type=rel.relationship_type,
                    source_column=rel.source_column,
                    target_column=rel.target_column,
                    dependency_distance=rel.dependency_distance,
                    metadata_json=json.dumps(rel.metadata, default=str),
                )
            )
        counts = Counter(o.object_type.lower() + "s" for o in catalog.objects)
        counts["columns"] = sum(len(o.metadata.get("columns", [])) for o in catalog.objects)
        counts["relationships"] = len(catalog.relationships)
        counts["objects"] = len(catalog.objects)
        candidate.schema_hash = fingerprint
        candidate.counts_json = json.dumps(counts)
        candidate.completeness_json = json.dumps(catalog.completeness)
        candidate.changes_json = json.dumps(
            {
                "structural_change": not previous or previous.schema_hash != fingerprint,
                "added": len(current_keys - previous_keys),
                "removed": len(previous_keys - current_keys),
            }
        )
        candidate.status = "READY"
        candidate.is_active = True
        candidate.completed_at = datetime.now(UTC)
        candidate.source_database = catalog.source_database or connection.database_name
        if previous:
            previous.is_active = False
        db.commit()
        db.refresh(candidate)
        return candidate
    except Exception as exc:
        db.rollback()
        failed = db.get(MetadataSnapshotModel, candidate.id)
        if failed:
            failed.status = "FAILED"
            failed.error_summary = f"{type(exc).__name__}: {str(exc)[:500]}"
            failed.completed_at = datetime.now(UTC)
            db.commit()
        raise
    finally:
        lock.release()


def snapshot_summary(snapshot: MetadataSnapshotModel | None) -> dict[str, Any]:
    if snapshot is None:
        return {
            "status": "NOT_DISCOVERED",
            "version": None,
            "last_refresh": None,
            "counts": {},
            "completeness": {},
        }
    return {
        "snapshot_id": snapshot.id,
        "status": snapshot.status,
        "version": snapshot.version,
        "last_refresh": snapshot.completed_at,
        "schema_hash": snapshot.schema_hash,
        "source_database": snapshot.source_database,
        "counts": json.loads(snapshot.counts_json),
        "completeness": json.loads(snapshot.completeness_json),
        "changes": json.loads(snapshot.changes_json),
        "error_summary": snapshot.error_summary,
    }


def schema_metadata_from_catalog(db: Session, snapshot: MetadataSnapshotModel) -> SchemaMetadata:
    objects = db.query(MetadataObjectModel).filter_by(snapshot_id=snapshot.id).all()
    relationships = db.query(MetadataRelationshipModel).filter_by(snapshot_id=snapshot.id).all()

    def names(kind: str) -> list[str]:
        return [
            f"{o.schema_name}.{o.object_name}" if o.schema_name else o.object_name
            for o in objects
            if o.object_type == kind
        ]

    table_schemas: dict[str, dict[str, Any]] = {}
    for obj in objects:
        if obj.object_type != "TABLE":
            continue
        name = f"{obj.schema_name}.{obj.object_name}" if obj.schema_name else obj.object_name
        detail = json.loads(obj.metadata_json)
        columns = [
            {
                "name": c.get("column_name"),
                "type": c.get("data_type"),
                "nullable": c.get("is_nullable"),
                "default": c.get("default_definition"),
            }
            for c in detail.get("columns", [])
        ]
        table_key = f"table:{name}".lower()
        foreign_keys = [
            {
                "name": json.loads(r.metadata_json).get("name"),
                "columns": [r.source_column],
                "referred_table": r.target_key.split(":", 1)[-1],
                "referred_columns": [r.target_column],
            }
            for r in relationships
            if r.source_key == table_key and r.relationship_type == "FOREIGN_KEY"
        ]
        indexes = [
            {
                "name": r.source_key.split(":", 1)[-1],
                "columns": [r.source_column],
                "unique": bool(json.loads(r.metadata_json).get("is_unique")),
            }
            for r in relationships
            if r.target_key == table_key and r.relationship_type == "INDEX_ON"
        ]
        primary_key = [
            r.source_column
            for r in relationships
            if r.target_key == table_key
            and r.relationship_type == "INDEX_ON"
            and json.loads(r.metadata_json).get("is_primary_key")
        ]
        table_schemas[name] = {
            "table_name": name,
            "columns": columns,
            "primary_key": primary_key,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
            "enrichment_loaded": True,
            "relationship_metadata_status": "catalog",
        }
    return SchemaMetadata(
        "sql_server",
        names("TABLE"),
        names("VIEW"),
        names("PROCEDURE"),
        snapshot.source_database,
        cache_diagnostics={
            "cache_hit": True,
            "cache_source": "persistent_metadata_catalog",
            "metadata_snapshot_id": snapshot.id,
            "metadata_snapshot_version": snapshot.version,
            "metadata_last_refreshed_at": snapshot.completed_at.isoformat()
            if snapshot.completed_at
            else None,
            "schema_hash": snapshot.schema_hash,
        },
        table_schemas=table_schemas,
    )
