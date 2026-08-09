from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import (
    EntityExtractionResult,
    StructuredBusinessIdentifier,
)
from legacydb_copilot.services.evidence_execution_service import execute_evidence_plan
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.safe_sql_service import PlannedQuery


@dataclass(frozen=True)
class EntityCandidate:
    identifier: str
    metadata: dict[str, Any]
    evidence_id: str
    table: str = ""
    column: str = ""


@dataclass(frozen=True)
class EntityResolution:
    extracted_value: str
    matched_value: str | None
    match_type: str
    confidence: float
    evidence_id: str
    candidates: list[EntityCandidate] = field(default_factory=list)
    reason: str = ""
    resolved_table: str = ""
    resolved_column: str = ""
    identifier_field: str = ""
    identifier_value: Any = None
    value_type: str = ""
    source_text: str = ""
    match_count: int = 0
    entity_probe: bool = False


@dataclass(frozen=True)
class EntityResolutionResult:
    status: str
    resolutions: list[EntityResolution]

    @property
    def can_continue(self) -> bool:
        return self.status == "resolved"


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*$")


def resolution_metadata_for_schema(
    connector, metadata: MetadataSearchResult, table_names: list[str]
) -> MetadataSearchResult:
    """Add active-schema tables to resolver lookup without changing object ranking."""
    tables = list(metadata.tables)
    known = {table.name.casefold() for table in tables}
    for table_name in table_names:
        if table_name.casefold() in known:
            continue
        try:
            schema = connector.get_table_schema(table_name)
        except Exception:
            continue
        tables.append(TableMetadata(
            table_name,
            [column["name"] for column in schema.get("columns", [])],
            0.0,
            schema.get("primary_key", []),
            schema.get("foreign_keys", []),
            schema.get("indexes", []),
        ))
        known.add(table_name.casefold())
    return MetadataSearchResult(
        tables=tables, views=metadata.views, procedures=metadata.procedures,
        version=metadata.version, engine_type=metadata.engine_type,
        candidate_trace=metadata.candidate_trace,
        metadata_cache_key=metadata.metadata_cache_key,
        target_object_not_found=metadata.target_object_not_found,
        failure_reason=metadata.failure_reason,
        exact_tables_requested=metadata.exact_tables_requested,
        exact_tables_found=metadata.exact_tables_found,
        exact_procedures_requested=metadata.exact_procedures_requested,
        exact_procedures_found=metadata.exact_procedures_found,
    )


def metadata_with_resolved_tables(
    metadata: MetadataSearchResult,
    resolution_metadata: MetadataSearchResult,
    result: EntityResolutionResult,
) -> MetadataSearchResult:
    """Promote database-proven entity tables into the downstream evidence scope."""
    resolved_names = {
        item.resolved_table.casefold() for item in result.resolutions if item.resolved_table
    }
    promoted = [
        table for table in resolution_metadata.tables
        if table.name.casefold() in resolved_names
    ]
    remaining = [
        table for table in metadata.tables
        if table.name.casefold() not in resolved_names
    ]
    return replace(metadata, tables=[*promoted, *remaining][:12])


def resolve_entities(connector, metadata: MetadataSearchResult, entities: EntityExtractionResult) -> EntityResolutionResult:
    """Resolve extracted identifiers using validated, bounded, read-only evidence queries."""
    structured = entities.structured_identifiers or []
    if structured:
        resolutions = [
            _resolve_structured(connector, metadata, identifier, index)
            for index, identifier in enumerate(structured, 1)
        ]
        statuses = {item.match_type for item in resolutions}
        status = (
            "ambiguous" if "ambiguous" in statuses
            else "blocked" if "blocked" in statuses
            else "not_found" if "not_found" in statuses
            else "resolved"
        )
        return EntityResolutionResult(status, resolutions)
    values = list(dict.fromkeys(
        entity.value for entity in entities.entities
        if entity.entity_type in {"business_identifier", "exact_id_or_code", "business_key"}
    ))
    resolutions = [_resolve_one(connector, metadata, value, index) for index, value in enumerate(values, 1)]
    statuses = {item.match_type for item in resolutions}
    if "ambiguous" in statuses:
        status = "ambiguous"
    elif "blocked" in statuses:
        status = "blocked"
    elif "not_found" in statuses:
        status = "not_found"
    else:
        status = "resolved"
    return EntityResolutionResult(status, resolutions)


def _canonical_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _qualified_table_parts(value: str) -> tuple[str, str]:
    parts = [part.strip("[]\"") for part in value.split(".")]
    return (parts[-2], parts[-1]) if len(parts) >= 2 else ("", parts[-1])


def _resolve_structured(
    connector,
    metadata: MetadataSearchResult,
    identifier: StructuredBusinessIdentifier,
    sequence: int,
) -> EntityResolution:
    targets: list[tuple[TableMetadata, str]] = []
    requested_column = _canonical_identifier(identifier.field_name)
    for table in metadata.tables:
        schema_name, table_name = _qualified_table_parts(table.name)
        if identifier.schema_name and schema_name.casefold() != identifier.schema_name.casefold():
            continue
        if identifier.table_name and table_name.casefold() != identifier.table_name.casefold():
            continue
        for column in table.columns:
            if _canonical_identifier(column) == requested_column:
                targets.append((table, column))
    if not targets:
        return EntityResolution(
            str(identifier.value), None, "not_found", 0.0, "",
            reason="The supplied identifier column was not found in active metadata.",
            identifier_field=identifier.field_name,
            identifier_value=identifier.value,
            value_type=identifier.value_type,
            source_text=identifier.source_text,
            entity_probe=True,
        )
    candidates, error = _execute_structured_lookup(
        connector, targets, identifier, sequence=sequence
    )
    if error:
        return EntityResolution(
            str(identifier.value), None, "blocked", 0.0, error[0], reason=error[1],
            identifier_field=identifier.field_name, identifier_value=identifier.value,
            value_type=identifier.value_type, source_text=identifier.source_text,
            entity_probe=True,
        )
    if len(candidates) == 1:
        match = candidates[0]
        return EntityResolution(
            str(identifier.value), match.identifier, "exact", identifier.confidence,
            match.evidence_id, candidates, "Exact metadata-validated field/value match.",
            match.table, match.column, identifier.field_name, identifier.value,
            identifier.value_type, identifier.source_text, 1, True,
        )
    if len(candidates) > 1:
        return EntityResolution(
            str(identifier.value), None, "ambiguous", 0.0, candidates[0].evidence_id,
            candidates, "Multiple exact rows or candidate tables matched the supplied identifier.",
            identifier_field=identifier.field_name, identifier_value=identifier.value,
            value_type=identifier.value_type, source_text=identifier.source_text,
            match_count=len(candidates), entity_probe=True,
        )
    return EntityResolution(
        str(identifier.value), None, "not_found", 0.0, "",
        reason="No row matched the supplied metadata-validated identifier.",
        identifier_field=identifier.field_name, identifier_value=identifier.value,
        value_type=identifier.value_type, source_text=identifier.source_text,
        match_count=0, entity_probe=True,
    )


def _execute_structured_lookup(
    connector,
    targets: list[tuple[TableMetadata, str]],
    identifier: StructuredBusinessIdentifier,
    *,
    sequence: int,
):
    plan: list[PlannedQuery] = []
    target_map: list[tuple[str, str, list[str]]] = []
    for table, column in targets:
        if not _IDENTIFIER.fullmatch(table.name) or not _IDENTIFIER.fullmatch(column):
            continue
        safe_columns = list(dict.fromkeys([column, *table.columns[:12]]))
        plan.append(
            PlannedQuery(
                purpose=f"Entity exact lookup in {table.name} by {column}",
                sql=f"SELECT {', '.join(safe_columns)} FROM {table.name} WHERE {column} = :entity_value",
                execution_sql=f"SELECT {', '.join(safe_columns)} FROM {table.name} WHERE {column} = :entity_value",
                parameters={"entity_value": identifier.value},
                evidence_semantics="entity_lookup",
                exact_cardinality=True,
                entity_table=table.name,
                identifier_column=column,
                identifier_value=identifier.value,
                row_scope="exact_identifier",
            )
        )
        target_map.append((table.name, column, safe_columns))
    evidence = execute_evidence_plan(connector, plan)
    candidates: list[EntityCandidate] = []
    errors: list[tuple[str, str]] = []
    for offset, item in enumerate(evidence):
        evidence_id = f"ENTITY-{sequence}-EXACT-{offset + 1}"
        if item.error:
            errors.append((evidence_id, item.error))
            continue
        table_name, key_column, safe_columns = target_map[offset]
        for row in item.rows:
            candidates.append(
                EntityCandidate(
                    str(row.get(key_column)),
                    {key: row.get(key) for key in safe_columns if key != key_column},
                    evidence_id,
                    table_name,
                    key_column,
                )
            )
    if errors and not candidates:
        return [], errors[0]
    return candidates, None


def _resolve_one(connector, metadata: MetadataSearchResult, value: str, sequence: int) -> EntityResolution:
    targets = [(table, column) for table in metadata.tables for column in _business_key_columns(table)]
    if not targets:
        return EntityResolution(value, None, "not_found", 0.0, "", reason="No safe business-key columns were discovered.")
    exact = _execute_lookup(connector, targets, value, exact=True, sequence=sequence)
    exact_candidates, exact_error = exact
    if exact_error:
        return EntityResolution(value, None, "blocked", 0.0, exact_error[0], reason=exact_error[1])
    exact_values = _unique_candidates(exact_candidates)
    if exact_values:
        matching = [candidate for candidate in exact_values if candidate.identifier.casefold() == value.casefold()]
        if matching:
            match = matching[0]
            return EntityResolution(value, match.identifier, "exact", 1.0, match.evidence_id, matching, "Exact database evidence match.", match.table, match.column)
    partial_candidates, partial_error = _execute_lookup(connector, targets, value, exact=False, sequence=sequence)
    if partial_error:
        return EntityResolution(value, None, "blocked", 0.0, partial_error[0], reason=partial_error[1])
    candidates = _unique_candidates(partial_candidates)
    direct_extensions = [
        candidate for candidate in candidates
        if _is_direct_canonical_extension(value, candidate.identifier)
    ]
    if len(direct_extensions) == 1:
        candidate = direct_extensions[0]
        return EntityResolution(
            value, candidate.identifier, "safe_partial", 0.9, candidate.evidence_id,
            candidates,
            "One direct canonical extension matched; prefixed related identifiers remained related evidence.",
            candidate.table, candidate.column,
        )
    if len(direct_extensions) > 1:
        return EntityResolution(
            value, None, "ambiguous", 0.0, direct_extensions[0].evidence_id,
            direct_extensions,
            "Multiple direct canonical extensions require user selection or human review.",
        )
    if len(candidates) == 1:
        candidate = candidates[0]
        return EntityResolution(value, candidate.identifier, "safe_partial", 0.85, candidate.evidence_id, candidates, "One bounded read-only candidate matched.", candidate.table, candidate.column)
    if len(candidates) > 1:
        return EntityResolution(value, None, "ambiguous", 0.0, candidates[0].evidence_id, candidates, "Multiple plausible database candidates require user selection or human review.")
    return EntityResolution(value, None, "not_found", 0.0, "", reason="No exact or safe partial database candidate matched.")


def _execute_lookup(connector, targets: list[tuple[TableMetadata, str]], value: str, *, exact: bool, sequence: int):
    escaped = value.replace("'", "''").replace("%", "[%]").replace("_", "[_]")
    plan: list[PlannedQuery] = []
    target_map: list[tuple[str, list[str]]] = []
    for table, column in targets:
        if not _IDENTIFIER.fullmatch(table.name) or not _IDENTIFIER.fullmatch(column):
            continue
        safe_columns = _safe_candidate_columns(table, column)
        engine = str(
            getattr(connector, "engine_type", "")
            or getattr(connector, "database_engine", "")
        ).lower()
        if "sql_server" in engine:
            comparable = f"CAST({column} AS NVARCHAR(MAX))"
        elif "mysql" in engine:
            comparable = f"CAST({column} AS CHAR)"
        else:
            comparable = f"CAST({column} AS TEXT)"
        comparison = (
            f"{comparable} = '{escaped}'"
            if exact
            else f"{comparable} LIKE '%{escaped}%'"
        )
        plan.append(PlannedQuery(f"Entity {'exact' if exact else 'candidate'} lookup", f"SELECT {', '.join(safe_columns)} FROM {table.name} WHERE {comparison}"))
        target_map.append((table.name, column, safe_columns))
    evidence = execute_evidence_plan(connector, plan)
    candidates: list[EntityCandidate] = []
    errors: list[tuple[str, str]] = []
    for offset, item in enumerate(evidence):
        evidence_id = f"ENTITY-{sequence}-{'EXACT' if exact else 'CANDIDATE'}-{offset + 1}"
        if item.error:
            errors.append((evidence_id, item.error))
            continue
        table_name, key_column, safe_columns = target_map[offset]
        for row in item.rows:
            identifier = str(row.get(key_column) or "").strip()
            if not identifier:
                continue
            candidates.append(EntityCandidate(identifier, {key: row.get(key) for key in safe_columns if key != key_column}, evidence_id, table_name, key_column))
    if errors and not candidates:
        return [], errors[0]
    return candidates, None


def _business_key_columns(table: TableMetadata) -> list[str]:
    primary = set(table.primary_key or [])
    columns = list(dict.fromkeys(
        column for column in table.columns
        if column in primary
        or re.search(
            r"(^id$|_id$|code$|(?:business)?key$|ref$|number$|reference$)",
            column,
            re.I,
        )
    ))
    return sorted(columns, key=_identifier_column_rank)


def _identifier_column_rank(column: str) -> tuple[int, str]:
    normalized = column.casefold().replace("_", "")
    if normalized == "businesskey":
        return (0, normalized)
    if normalized.endswith("number"):
        return (1, normalized)
    if normalized.endswith(("code", "key", "reference", "ref")):
        return (2, normalized)
    if normalized.endswith("id"):
        return (3, normalized)
    if normalized.endswith("name"):
        return (5, normalized)
    return (4, normalized)


def _safe_candidate_columns(table: TableMetadata, key_column: str) -> list[str]:
    contextual = [column for column in table.columns if re.search(r"status|state|stage|type|created|updated|timestamp|date", column, re.I)]
    return list(dict.fromkeys([key_column, *contextual[:4]]))


def _unique_candidates(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    unique: dict[str, EntityCandidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.identifier.casefold(), candidate)
    return list(unique.values())


def _is_direct_canonical_extension(extracted: str, candidate: str) -> bool:
    """Recognize a suffix completion but never a prefixed related identifier."""
    base = extracted.casefold().rstrip("-_/ ")
    value = candidate.casefold()
    return any(value.startswith(base + separator) for separator in ("-", "_", "/", " "))
