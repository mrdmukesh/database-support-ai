from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult

_NOISE_TOKENS = {
    "analyze",
    "explain",
    "index",
    "indexes",
    "logic",
    "optimization",
    "recommend",
    "row",
    "rows",
    "scan",
    "scans",
    "stored",
    "procedure",
}

@dataclass(frozen=True)
class TableMetadata:
    name: str
    columns: list[str]
    score: float
    primary_key: list[str] | None = None
    foreign_keys: list[dict[str, Any]] | None = None
    indexes: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class MetadataSearchResult:
    tables: list[TableMetadata]
    views: list[str]
    procedures: list[str]
    version: str
    engine_type: str | None = None
    candidate_trace: list[dict[str, Any]] = field(default_factory=list)
    metadata_cache_key: str = ""
    target_object_not_found: bool = False
    failure_reason: str = ""
    exact_tables_requested: list[str] = field(default_factory=list)
    exact_tables_found: list[str] = field(default_factory=list)
    exact_procedures_requested: list[str] = field(default_factory=list)
    exact_procedures_found: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MetadataSearchContext:
    organization_id: str
    workspace_id: str
    connection_id: str
    database_name: str
    schema_name: str = ""
    connection_string_database: str = ""
    actual_database: str = ""
    connector_cache_key: str = ""

    @property
    def cache_key(self) -> str:
        return "|".join(
            [
                self.organization_id,
                self.workspace_id,
                self.connection_id,
                self.database_name.lower(),
            ]
        )


def _tokens(question: str, entities: EntityExtractionResult) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for tokens within metadata_search_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in metadata_search_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    raw = question.lower().replace("_", " ").replace("-", " ").split()
    tokens = {
        token.strip(".,:;()[]{}")
        for token in raw
        if len(token.strip(".,:;()[]{}")) >= 3
        and token.strip(".,:;()[]{}") not in _NOISE_TOKENS
    }
    for entity in entities.entities:
        tokens.update(
            token
            for token in entity.value.lower().replace("-", " ").split()
            if token not in _NOISE_TOKENS
        )
    if entities.likely_module:
        tokens.add(entities.likely_module.lower())
    if entities.suspected_issue:
        tokens.update(entities.suspected_issue.lower().split())
    words = re.findall(r"[A-Za-z]+", question)
    for size in range(2, min(4, len(words)) + 1):
        for index in range(len(words) - size + 1):
            phrase = words[index:index + size]
            acronym = "".join(word[0] for word in phrase).lower()
            if len(acronym) >= 3:
                tokens.add(acronym)
    return tokens


def query_relevance_terms(question: str, entities: EntityExtractionResult) -> set[str]:
    """Return normalized, query-derived terms used consistently across metadata and definition search."""
    return _tokens(question, entities)


def _identifier_parts(value: str) -> set[str]:
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()
    parts = {part for part in re.split(r"[^a-z0-9]+", raw) if len(part) >= 2}
    expanded = set(parts)
    for part in parts:
        if part.endswith("ies") and len(part) > 4:
            expanded.add(part[:-3] + "y")
        if part.endswith("s") and len(part) > 3:
            expanded.add(part[:-1])
    return expanded


def _concept_tokens(entities: EntityExtractionResult) -> set[str]:
    concepts: set[str] = set()
    for entity in entities.entities:
        if entity.entity_type in {"possible_table", "possible_column", "possible_table_or_column", "stored_procedure"}:
            concepts.update(_identifier_parts(entity.value))
    concepts.update(
        token
        for keyword in entities.business_keywords or []
        for token in _identifier_parts(keyword)
        if token not in _NOISE_TOKENS
    )
    return {token for token in concepts if token not in _NOISE_TOKENS}


def _business_identifiers(entities: EntityExtractionResult) -> list[str]:
    return [
        entity.value
        for entity in entities.entities
        if entity.entity_type in {"business_identifier", "exact_id_or_code", "business_key"}
    ]


def _explicit_names(question: str, label: str) -> set[str]:
    names: set[str] = set()
    pattern = rf"\b{label}\s*:\s*([a-zA-Z_][a-zA-Z0-9_]*)\b"
    names.update(match.group(1).lower() for match in re.finditer(pattern, question, re.I))
    return names


def _key_columns(table_name: str, columns: list[str], primary_key: list[str] | None, foreign_keys: list[dict[str, Any]] | None) -> set[str]:
    keys = {column.lower() for column in primary_key or []}
    for fk in foreign_keys or []:
        keys.update(str(column).lower() for column in fk.get("columns", []))
        if fk.get("column"):
            keys.add(str(fk["column"]).lower())
    keys.update(
        column.lower()
        for column in columns
        if re.search(r"(^id$|_id$|_code$|_key$|_ref$|number$|reference)", column.lower())
    )
    table_parts = _identifier_parts(table_name)
    keys.update(column.lower() for column in columns if _identifier_parts(column) & table_parts and column.lower().endswith("_id"))
    return keys


def _table_score_components(
    *,
    table_name: str,
    columns: list[str],
    primary_key: list[str] | None,
    foreign_keys: list[dict[str, Any]] | None,
    question_tokens: set[str],
    concept_tokens: set[str],
    business_ids: list[str],
) -> dict[str, float]:
    table_parts = _identifier_parts(table_name)
    column_parts = {column: _identifier_parts(column) for column in columns}
    table_name_relevance = 4.0 * len((question_tokens | concept_tokens) & table_parts)
    column_name_relevance = 0.0
    for parts in column_parts.values():
        hits = (question_tokens | concept_tokens) & parts
        if hits:
            column_name_relevance += min(3.0, 1.5 * len(hits))
    keys = _key_columns(table_name, columns, primary_key, foreign_keys)
    key_relevance = 0.0
    for column in keys:
        parts = _identifier_parts(column)
        if parts & (question_tokens | concept_tokens):
            key_relevance += 2.0
    relationship_relevance = 1.0 if foreign_keys else 0.0
    return {
        "table_name_relevance": table_name_relevance,
        "column_name_relevance": column_name_relevance,
        "key_relevance": key_relevance,
        "relationship_relevance": relationship_relevance,
    }


def search_metadata(
    connector,
    question: str,
    entities: EntityExtractionResult,
    context: MetadataSearchContext | None = None,
    schema_metadata: Any | None = None,
) -> MetadataSearchResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles search metadata within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    metadata = schema_metadata or connector.get_schema_metadata()
    tokens = _tokens(question, entities)
    concepts = _concept_tokens(entities)
    business_ids = _business_identifiers(entities)
    explicit_tables = _explicit_names(question, "table")
    explicit_procedures = _explicit_names(question, "procedure") | {
        entity.value.lower()
        for entity in entities.entities
        if entity.entity_type == "stored_procedure"
    }
    exact_table_names = {table.lower(): table for table in metadata.tables}
    exact_table_matches = {exact_table_names[name].lower() for name in explicit_tables if name in exact_table_names}
    exact_proc_names = {proc.lower(): proc for proc in metadata.procedures}
    exact_proc_matches = {exact_proc_names[name].lower() for name in explicit_procedures if name in exact_proc_names}
    missing_tables = sorted(explicit_tables - set(exact_table_matches))
    missing_procedures = sorted(explicit_procedures - set(exact_proc_matches))
    target_object_not_found = bool(missing_tables or missing_procedures)
    failure_reason = ""
    if missing_tables:
        failure_reason += "TARGET_OBJECT_NOT_FOUND: explicit table(s) not found in active metadata: " + ", ".join(missing_tables)
    if missing_procedures:
        failure_reason += ("; " if failure_reason else "TARGET_OBJECT_NOT_FOUND: ") + "explicit procedure(s) not found in active metadata: " + ", ".join(missing_procedures)
    tables: list[TableMetadata] = []
    trace: list[dict[str, Any]] = []
    if context:
        trace.append(
            {
                "object_type": "metadata_context",
                "name": context.connection_id,
                "score": "",
                "decision": "active",
                "reason": (
                    f"workspace_id={context.workspace_id}; connection_id={context.connection_id}; "
                    f"database={context.database_name}; schema={context.schema_name or 'default'}; "
                    f"connection_string_database={context.connection_string_database or 'unknown'}; "
                    f"metadata_cache_key={context.cache_key}; "
                    f"expected_database={context.database_name}; actual_database={context.actual_database or 'unknown'}; "
                    f"connector_cache_key={context.connector_cache_key}; "
                    f"exact_tables_requested={sorted(explicit_tables)}; exact_tables_found={sorted(exact_table_matches)}; "
                    f"exact_procedures_requested={sorted(explicit_procedures)}; exact_procedures_found={sorted(exact_proc_matches)}; "
                    f"failure_reason={failure_reason or 'none'}"
                ),
            }
        )
    if target_object_not_found:
        for name in missing_tables:
            trace.append(
                {
                    "object_type": "table",
                    "name": name,
                    "score": 0,
                    "decision": "rejected",
                    "reason": "TARGET_OBJECT_NOT_FOUND: explicit table is absent from active database metadata",
                }
            )
        for name in missing_procedures:
            trace.append(
                {
                    "object_type": "procedure",
                    "name": name,
                    "score": 0,
                    "decision": "rejected",
                    "reason": "TARGET_OBJECT_NOT_FOUND: explicit procedure is absent from active database metadata",
                }
            )
        return MetadataSearchResult(
            tables=[],
            views=[],
            procedures=[],
            version=metadata.version,
            engine_type=metadata.engine_type,
            candidate_trace=trace,
            metadata_cache_key=context.cache_key if context else "",
            target_object_not_found=True,
            failure_reason=failure_reason,
            exact_tables_requested=sorted(explicit_tables),
            exact_tables_found=sorted(exact_table_matches),
            exact_procedures_requested=sorted(explicit_procedures),
            exact_procedures_found=sorted(exact_proc_matches),
        )
    for table_name in metadata.tables:
        try:
            schema = connector.get_table_schema(table_name)
            columns = [column["name"] for column in schema["columns"]]
            primary_key = schema.get("primary_key", [])
            foreign_keys = schema.get("foreign_keys", [])
            indexes = schema.get("indexes", [])
        except Exception:
            columns = []
            primary_key = []
            foreign_keys = []
            indexes = []
        components = _table_score_components(
            table_name=table_name,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            question_tokens=tokens,
            concept_tokens=concepts,
            business_ids=business_ids,
        )
        score = round(sum(components.values()), 2)
        decision = "selected" if score > 0 else "rejected"
        reason_bits = [
            f"{name.replace('_', ' ')}={value:g}"
            for name, value in components.items()
            if value > 0
        ]
        if not reason_bits:
            reason_bits.append("no exact/normalized metadata, key, or relationship match")
        trace.append(
            {
                "object_type": "table",
                "name": table_name,
                "score": score,
                "decision": decision,
                "reason": "; ".join(reason_bits),
                "components": components,
            }
        )
        if table_name.lower() in exact_table_matches:
            score += 100.0
            decision = "selected"
            trace[-1]["score"] = score
            trace[-1]["decision"] = decision
            trace[-1]["reason"] = "explicit table name exists in active database metadata; semantic alternatives deferred"
        if exact_table_matches and table_name.lower() not in exact_table_matches:
            trace[-1]["decision"] = "rejected"
            trace[-1]["reason"] += "; exact user table match exists, so semantic alternative was not selected"
            continue
        if score > 0:
            tables.append(
                TableMetadata(
                    name=table_name,
                    columns=columns,
                    score=score,
                    primary_key=primary_key,
                    foreign_keys=foreign_keys,
                    indexes=indexes,
                )
            )
    tables.sort(key=lambda item: (item.score, item.name), reverse=True)
    relevance_required = bool(business_ids)
    if not tables and metadata.tables and not relevance_required:
        table_trace = [item for item in trace if item.get("object_type") == "table"]
        fallback_names = {item["name"] for item in sorted(table_trace, key=lambda item: (item["score"], item["name"]), reverse=True)[:5]}
        for table_name in metadata.tables:
            if table_name not in fallback_names:
                continue
            try:
                schema = connector.get_table_schema(table_name)
                columns = [column["name"] for column in schema["columns"]]
                primary_key = schema.get("primary_key", [])
                foreign_keys = schema.get("foreign_keys", [])
                indexes = schema.get("indexes", [])
            except Exception:
                columns = []
                primary_key = []
                foreign_keys = []
                indexes = []
            tables.append(TableMetadata(table_name, columns, 0.0, primary_key, foreign_keys, indexes))
        for item in trace:
            if item["name"] in fallback_names:
                item["decision"] = "selected"
                item["reason"] += "; fallback for insufficient metadata match, requires proof before RCA"
    proc_tokens = tokens | concepts
    exact_procs = {
        entity.value.lower()
        for entity in entities.entities
        if entity.entity_type == "stored_procedure"
    }
    selected_table_tokens = {part for table in tables[:8] for part in _identifier_parts(table.name)}
    procedures = [
        proc
        for proc in metadata.procedures
        if proc.lower() in explicit_procedures
        or proc.lower() in exact_procs
        or any(token in proc.lower() for token in proc_tokens | selected_table_tokens)
    ]
    if explicit_procedures or exact_procs:
        exact_requested = explicit_procedures | exact_procs
        for proc in metadata.procedures:
            trace.append(
                {
                    "object_type": "procedure",
                    "name": proc,
                    "score": 100 if proc.lower() in exact_requested else 0,
                    "decision": "selected" if proc.lower() in exact_requested else "rejected",
                    "reason": (
                        "explicit procedure exists in active database metadata"
                        if proc.lower() in exact_requested
                        else "exact user procedure match exists, so semantic alternative was not selected"
                    ),
                }
            )
        procedures = [proc for proc in metadata.procedures if proc.lower() in exact_procs]
        if explicit_procedures:
            procedures = [proc for proc in metadata.procedures if proc.lower() in explicit_procedures]
    if not procedures:
        procedures = [] if explicit_procedures or exact_procs or relevance_required else metadata.procedures[:20]
    views = [view for view in metadata.views if any(token in view.lower() for token in tokens)]
    if not views and not relevance_required:
        views = metadata.views[:10]
    selected_names = {table.name for table in tables[:8]}
    for item in trace:
        if item["object_type"] == "table" and item["name"] not in selected_names and item["decision"] == "selected":
            item["decision"] = "rejected"
            item["reason"] += "; outside top scored metadata candidates"
    return MetadataSearchResult(
        tables=tables[:8],
        views=views[:10],
        procedures=procedures[:20],
        version=metadata.version,
        engine_type=metadata.engine_type,
        candidate_trace=trace,
        metadata_cache_key=context.cache_key if context else "",
        target_object_not_found=False,
        failure_reason="",
        exact_tables_requested=sorted(explicit_tables),
        exact_tables_found=sorted(exact_table_matches),
        exact_procedures_requested=sorted(explicit_procedures),
        exact_procedures_found=sorted(exact_proc_matches),
    )


def rows_as_text(rows: list[dict[str, Any]], limit: int = 5) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles rows as text within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    if not rows:
        return "No rows returned."
    return "\n".join("; ".join(f"{k}={v}" for k, v in row.items()) for row in rows[:limit])
