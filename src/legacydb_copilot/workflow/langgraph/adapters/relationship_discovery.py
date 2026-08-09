from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis
from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.enums import (
    EntityResolutionStatus,
    ObjectDisposition,
    RelationshipVerification,
)
from legacydb_copilot.workflow.langgraph.state import (
    DatabaseObjectRef,
    EvidenceGapRecord,
    InvestigationState,
    RelationshipEdge,
)


@dataclass(frozen=True)
class InferredRelationship:
    source_object: str
    source_column: str
    target_object: str
    target_column: str
    relationship_type: str = "business_key"
    source: str = "existing_metadata_inference"


@dataclass(frozen=True)
class DiscoverySnapshot:
    metadata: MetadataSearchResult
    procedures: tuple[ProcedureAnalysis, ...] = ()
    view_dependencies: dict[str, tuple[str, ...]] = field(default_factory=dict)
    inferred_relationships: tuple[InferredRelationship, ...] = ()
    inaccessible_objects: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationshipDiscoveryAdapter:
    """Bound and translate existing metadata-service output; never execute objects."""

    snapshot_provider: Callable[[InvestigationState], DiscoverySnapshot]
    authorize: Callable[[InvestigationState], None]
    max_depth: int = 3
    max_objects: int = 25

    def __post_init__(self) -> None:
        if self.max_depth < 0 or self.max_objects < 1:
            raise ValueError("Discovery limits must be positive and bounded")

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        if state["entity_resolution_status"] != EntityResolutionStatus.RESOLVED:
            return {}
        try:
            self.authorize(state)
            snapshot = self.snapshot_provider(state)
        except PermissionError as exc:
            raise OperationalNodeError(
                "METADATA_ACCESS_DENIED",
                "Metadata access was denied for the authorized workspace scope.",
                context={"workspace_id": state["workspace_id"], "detail": str(exc)},
            ) from exc
        except OperationalNodeError:
            raise
        except Exception as exc:
            raise OperationalNodeError(
                "METADATA_DISCOVERY_UNAVAILABLE",
                "Metadata discovery service is temporarily unavailable.",
                retryable=True,
                context={"workspace_id": state["workspace_id"], "detail": str(exc)},
            ) from exc
        return self._translate(state, snapshot)

    def _translate(self, state: InvestigationState, snapshot: DiscoverySnapshot) -> dict[str, Any]:
        tables = {_key(table.name): table for table in snapshot.metadata.tables}
        seeds = [entity.table for entity in state["resolved_entities"] if entity.table] + list(
            state["requested_objects"]
        )
        selected_keys: list[str] = []
        edges: list[RelationshipEdge] = []
        gaps: list[EvidenceGapRecord] = []
        queue = deque((name, 0) for name in seeds)
        visited: set[str] = set()
        edge_keys: set[tuple[str, str, str, str, str]] = set()
        depth_limited = False
        object_limited = False

        while queue:
            name, distance = queue.popleft()
            key = _key(name)
            if key in visited:
                continue
            if len(visited) >= self.max_objects:
                object_limited = True
                break
            table = tables.get(key)
            if table is None:
                gaps.append(
                    _gap("missing_object", f"Metadata was not found for {name}.", name, True)
                )
                continue
            visited.add(key)
            selected_keys.append(key)
            for edge in _table_edges(table):
                self._add_edge(edges, edge_keys, edge)
                neighbor = edge.target_object
                if _key(neighbor) == key:
                    continue
                if distance >= self.max_depth:
                    depth_limited = True
                else:
                    queue.append((neighbor, distance + 1))

        for relation in snapshot.inferred_relationships:
            if _key(relation.source_object) in visited or _key(relation.target_object) in visited:
                self._add_edge(
                    edges,
                    edge_keys,
                    RelationshipEdge(
                        source_object=relation.source_object,
                        source_column=relation.source_column,
                        target_object=relation.target_object,
                        target_column=relation.target_column,
                        relationship_type=relation.relationship_type,
                        verification=RelationshipVerification.INFERRED,
                        source=relation.source,
                    ),
                )

        objects = [
            _table_object(tables[key], required=index == 0, distance=index)
            for index, key in enumerate(selected_keys)
        ]
        for view, dependencies in snapshot.view_dependencies.items():
            if any(_key(item) in visited for item in dependencies):
                objects.append(_object(view, "VIEW", "Existing view dependency metadata.", False))
                for dependency in dependencies:
                    self._add_edge(
                        edges,
                        edge_keys,
                        RelationshipEdge(
                            source_object=view,
                            source_column="",
                            target_object=dependency,
                            target_column="",
                            relationship_type="view_dependency",
                            verification=RelationshipVerification.VERIFIED,
                            source="metadata_service",
                        ),
                    )
        for procedure in snapshot.procedures:
            dependencies = [*procedure.tables_read, *procedure.tables_written]
            if not any(_key(item) in visited for item in dependencies):
                continue
            mutates = bool(
                procedure.tables_written
                or procedure.insert_statements
                or procedure.update_statements
                or procedure.delete_statements
                or procedure.merge_statements
            )
            objects.append(
                _object(
                    procedure.name,
                    procedure.object_type,
                    "Existing procedure dependency analysis.",
                    False,
                    inspection_only=True,
                    contains_mutation=mutates,
                    contains_dynamic_sql=procedure.dynamic_sql,
                    unsafe_to_execute=mutates or procedure.dynamic_sql,
                    path_role=(
                        "BOTH"
                        if procedure.tables_read and procedure.tables_written
                        else "WRITE"
                        if procedure.tables_written
                        else "READ"
                    ),
                )
            )
            for dependency in dependencies:
                kind = (
                    "procedure_write_dependency"
                    if dependency in procedure.tables_written
                    else "procedure_read_dependency"
                )
                self._add_edge(
                    edges,
                    edge_keys,
                    RelationshipEdge(
                        source_object=procedure.name,
                        source_column="",
                        target_object=dependency,
                        target_column="",
                        relationship_type=kind,
                        verification=RelationshipVerification.VERIFIED,
                        source="stored_procedure_intelligence",
                    ),
                )
        for name in snapshot.inaccessible_objects:
            gaps.append(
                _gap(
                    "metadata_permission",
                    f"Metadata permission was unavailable for {name}.",
                    name,
                    False,
                )
            )
        if snapshot.metadata.target_object_not_found:
            gaps.append(
                _gap(
                    "missing_object",
                    snapshot.metadata.failure_reason or "Requested object was not found.",
                    "",
                    True,
                )
            )
        if depth_limited:
            gaps.append(
                _gap(
                    "depth_limit",
                    f"Relationship traversal stopped at depth {self.max_depth}.",
                    "",
                    False,
                )
            )
        if object_limited:
            gaps.append(
                _gap(
                    "object_limit",
                    f"Relationship discovery stopped at {self.max_objects} objects.",
                    "",
                    False,
                )
            )
        unique_objects = _dedupe_objects(objects)[: self.max_objects]
        required = [
            item for item in unique_objects if item.disposition == ObjectDisposition.REQUIRED
        ]
        optional = [
            item for item in unique_objects if item.disposition == ObjectDisposition.OPTIONAL
        ]
        return {
            "candidate_objects": unique_objects,
            "selected_objects": unique_objects,
            "required_objects": required,
            "optional_objects": optional,
            "relationship_edges": edges,
            "metadata_gaps": gaps,
            "object_count": len(unique_objects),
        }

    @staticmethod
    def _add_edge(
        edges: list[RelationshipEdge],
        keys: set[tuple[str, str, str, str, str]],
        edge: RelationshipEdge,
    ) -> None:
        key = (
            edge.source_object.casefold(),
            edge.source_column.casefold(),
            edge.target_object.casefold(),
            edge.target_column.casefold(),
            edge.relationship_type.casefold(),
        )
        if key not in keys:
            keys.add(key)
            edges.append(edge)


def _table_edges(table: TableMetadata) -> list[RelationshipEdge]:
    edges: list[RelationshipEdge] = []
    for fk in table.foreign_keys or []:
        source_columns = fk.get("columns") or ()
        target_columns = fk.get("referred_columns") or ()
        target = str(fk.get("referred_table") or "")
        for index, source_column in enumerate(source_columns):
            target_column = str(target_columns[index]) if index < len(target_columns) else ""
            edges.append(
                RelationshipEdge(
                    source_object=table.name,
                    source_column=str(source_column),
                    target_object=target,
                    target_column=target_column,
                    relationship_type="self_foreign_key"
                    if _key(target) == _key(table.name)
                    else "foreign_key",
                    verification=RelationshipVerification.VERIFIED,
                    source="metadata_service",
                )
            )
    for column in table.primary_key or []:
        edges.append(
            RelationshipEdge(
                source_object=table.name,
                source_column=str(column),
                target_object=table.name,
                target_column=str(column),
                relationship_type="primary_key",
                verification=RelationshipVerification.VERIFIED,
                source="metadata_service",
            )
        )
    for index in table.indexes or []:
        if index.get("unique"):
            for column in index.get("column_names") or index.get("columns") or ():
                edges.append(
                    RelationshipEdge(
                        source_object=table.name,
                        source_column=str(column),
                        target_object=table.name,
                        target_column=str(column),
                        relationship_type="unique_key",
                        verification=RelationshipVerification.VERIFIED,
                        source="metadata_service",
                    )
                )
    return edges


def _parts(name: str) -> tuple[str, str, str]:
    parts = [part.strip('[]`"') for part in name.split(".")]
    if len(parts) >= 3:
        return parts[-3], parts[-2], parts[-1]
    if len(parts) == 2:
        return "", parts[0], parts[1]
    return "", "", parts[0]


def _key(name: str) -> str:
    return name.strip('[]`"').casefold()


def _object(
    name: str, object_type: str, reason: str, required: bool, **flags: Any
) -> DatabaseObjectRef:
    database, schema, object_name = _parts(name)
    return DatabaseObjectRef(
        database=database,
        schema_name=schema,
        object_name=object_name,
        object_type=object_type,
        relevance_reason=reason,
        disposition=ObjectDisposition.REQUIRED if required else ObjectDisposition.OPTIONAL,
        relationship_verification=RelationshipVerification.VERIFIED,
        **flags,
    )


def _table_object(table: TableMetadata, *, required: bool, distance: int) -> DatabaseObjectRef:
    value = _object(table.name, "TABLE", "Resolved entity or verified relationship.", required)
    return value.model_copy(update={"dependency_distance": distance})


def _dedupe_objects(objects: list[DatabaseObjectRef]) -> list[DatabaseObjectRef]:
    result: dict[tuple[str, str], DatabaseObjectRef] = {}
    for item in objects:
        result.setdefault((item.qualified_name.casefold(), item.object_type.casefold()), item)
    return list(result.values())


def _gap(kind: str, description: str, affected_object: str, blocking: bool) -> EvidenceGapRecord:
    return EvidenceGapRecord(
        gap_type=kind,
        description=description,
        affected_object=affected_object,
        blocking=blocking,
        source_node="discover_objects",
        timestamp=datetime.now(UTC),
    )
