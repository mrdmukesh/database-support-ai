from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.services.evidence_execution_service import execute_evidence_plan
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.safe_sql_service import PlannedQuery


@dataclass(frozen=True)
class EntityCandidate:
    identifier: str
    metadata: dict[str, Any]
    evidence_id: str


@dataclass(frozen=True)
class EntityResolution:
    extracted_value: str
    matched_value: str | None
    match_type: str
    confidence: float
    evidence_id: str
    candidates: list[EntityCandidate] = field(default_factory=list)
    reason: str = ""


@dataclass(frozen=True)
class EntityResolutionResult:
    status: str
    resolutions: list[EntityResolution]

    @property
    def can_continue(self) -> bool:
        return self.status == "resolved"


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*$")


def resolve_entities(connector, metadata: MetadataSearchResult, entities: EntityExtractionResult) -> EntityResolutionResult:
    """Resolve extracted identifiers using validated, bounded, read-only evidence queries."""
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
            return EntityResolution(value, matching[0].identifier, "exact", 1.0, matching[0].evidence_id, matching, "Exact database evidence match.")
    partial_candidates, partial_error = _execute_lookup(connector, targets, value, exact=False, sequence=sequence)
    if partial_error:
        return EntityResolution(value, None, "blocked", 0.0, partial_error[0], reason=partial_error[1])
    candidates = _unique_candidates(partial_candidates)
    if len(candidates) == 1:
        candidate = candidates[0]
        return EntityResolution(value, candidate.identifier, "safe_partial", 0.85, candidate.evidence_id, candidates, "One bounded read-only candidate matched.")
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
        comparison = f"{column} = '{escaped}'" if exact else f"{column} LIKE '%{escaped}%'"
        plan.append(PlannedQuery(f"Entity {'exact' if exact else 'candidate'} lookup", f"SELECT {', '.join(safe_columns)} FROM {table.name} WHERE {comparison}"))
        target_map.append((column, safe_columns))
    evidence = execute_evidence_plan(connector, plan)
    candidates: list[EntityCandidate] = []
    errors: list[tuple[str, str]] = []
    for offset, item in enumerate(evidence):
        evidence_id = f"ENTITY-{sequence}-{'EXACT' if exact else 'CANDIDATE'}-{offset + 1}"
        if item.error:
            errors.append((evidence_id, item.error))
            continue
        key_column, safe_columns = target_map[offset]
        for row in item.rows:
            identifier = str(row.get(key_column) or "").strip()
            if not identifier:
                continue
            candidates.append(EntityCandidate(identifier, {key: row.get(key) for key in safe_columns if key != key_column}, evidence_id))
    if errors and not candidates:
        return [], errors[0]
    return candidates, None


def _business_key_columns(table: TableMetadata) -> list[str]:
    primary = set(table.primary_key or [])
    return list(dict.fromkeys(
        column for column in table.columns
        if column in primary or re.search(r"(^id$|_id$|_code$|_key$|_ref$|_number$|reference$)", column, re.I)
    ))


def _safe_candidate_columns(table: TableMetadata, key_column: str) -> list[str]:
    contextual = [column for column in table.columns if re.search(r"status|state|stage|type|created|updated|timestamp|date", column, re.I)]
    return list(dict.fromkeys([key_column, *contextual[:4]]))


def _unique_candidates(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    unique: dict[str, EntityCandidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.identifier.casefold(), candidate)
    return list(unique.values())
