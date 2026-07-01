from __future__ import annotations

import re
from dataclasses import dataclass

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.problem_phrase_service import parse_problem_phrase, resolve_table_from_terms, terms_match_table


@dataclass(frozen=True)
class PlannedQuery:
    purpose: str
    sql: str
    risk: str = "Read-only"


@dataclass(frozen=True)
class MissingChildFlow:
    parent_table: TableMetadata
    child_table: TableMetadata
    parent_id: str
    parent_label: str
    parent_status: str | None
    child_id: str
    child_fk_to_parent: str
    child_label: str | None


@dataclass(frozen=True)
class DuplicateChildFlow:
    parent_table: TableMetadata
    child_table: TableMetadata
    parent_id: str
    parent_label: str
    child_fk_to_parent: str
    child_label: str | None
    child_status: str | None
    parent_key_value: str | None


_DESTRUCTIVE = re.compile(r"\b(insert|update|delete|drop|alter|truncate|call|exec|execute|merge|replace|create|grant|revoke)\b", re.I)


def validate_read_only_sql(sql: str) -> None:
    stripped = sql.strip().rstrip(";")
    if not re.match(r"^(select|show|describe|desc|explain)\b", stripped, re.I):
        raise ValueError("Only SELECT, SHOW, DESCRIBE, and EXPLAIN statements are allowed")
    if _DESTRUCTIVE.search(stripped):
        raise ValueError("Unsafe SQL command rejected")


def ensure_limit(sql: str, limit: int = 25) -> str:
    stripped = sql.strip().rstrip(";")
    return stripped


def _where_for_table(table: TableMetadata, entities: EntityExtractionResult, engine_type: str | None = None) -> str:
    filters: list[str] = []
    business_values = [
        entity.value
        for entity in entities.entities
        if entity.entity_type in {"business_key", "exact_id_or_code", "status_or_code"}
    ]
    for value in business_values:
        escaped = value.replace("'", "''")
        column_filters = []
        for column in table.columns:
            column_l = column.lower()
            if any(term in column_l for term in ("number", "code", "status", "key", "reference", "name", "message")):
                column_filters.append(f"{_cast_to_text(column, engine_type)} = '{escaped}'")
        if column_filters:
            filters.append("(" + " OR ".join(column_filters[:6]) + ")")
    return " WHERE " + " OR ".join(filters) if filters else ""


def _find_column(table: TableMetadata, required_terms: tuple[str, ...], optional_terms: tuple[str, ...] = ()) -> str | None:
    candidates = []
    for column in table.columns:
        lowered = column.lower()
        if all(term in lowered for term in required_terms):
            score = len(required_terms) * 2 + sum(1 for term in optional_terms if term in lowered)
            candidates.append((score, len(column), column))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][2]


def _missing_target_terms(entities: EntityExtractionResult) -> set[str]:
    stop = {"missing", "records", "record", "where", "with", "without", "find", "show", "group", "root", "cause", "caused"}
    terms = {term.lower() for term in (entities.business_keywords or []) if len(term) >= 3 and term.lower() not in stop}
    for entity in entities.entities:
        terms.update(part.lower() for part in re.split(r"[^a-zA-Z0-9]+", entity.value) if len(part) >= 3)
    return terms


def _duplicate_target_terms(entities: EntityExtractionResult) -> set[str]:
    stop = {"duplicate", "duplicates", "multiple", "active", "open", "valid", "created", "create", "where", "with", "why", "did", "two"}
    terms = {term.lower() for term in (entities.business_keywords or []) if len(term) >= 3 and term.lower() not in stop}
    return terms


def _infer_missing_child_flow(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> MissingChildFlow | None:
    question_text = " ".join(entities.business_keywords or [])
    problem = parse_problem_phrase(question_text)
    parsed_terms = set(problem.target_terms)
    terms = parsed_terms or _missing_target_terms(entities)
    if not terms:
        return None
    resolved_child = resolve_table_from_terms(list(terms), metadata)
    child_candidates = sorted(
        metadata.tables,
        key=lambda table: (
            10 if resolved_child and table.name == resolved_child.name else 0,
            sum(1 for term in terms if term in table.name.lower() or any(term in col.lower() for col in table.columns)),
        ),
        reverse=True,
    )
    for child in child_candidates:
        if not terms_match_table(list(terms), child) and not any(term in child.name.lower() or any(term in col.lower() for col in child.columns) for term in terms):
            continue
        child_id = _find_column(child, ("id",))
        child_label = _find_column(child, ("number",)) or _find_column(child, ("name",)) or _find_column(child, ("code",))
        if not child_id:
            continue
        for fk in child.foreign_keys or []:
            parent_name = str(fk.get("referred_table") or "")
            parent_cols = fk.get("referred_columns") or []
            child_cols = fk.get("columns") or fk.get("constrained_columns") or []
            parent = next((table for table in metadata.tables if table.name.lower() == parent_name.lower()), None)
            if not parent or not parent_cols or not child_cols:
                continue
            if problem.parent_terms and not terms_match_table(problem.parent_terms, parent):
                continue
            parent_id = str(parent_cols[0])
            child_fk = str(child_cols[0])
            parent_label = _find_column(parent, ("number",)) or _find_column(parent, ("name",)) or _find_column(parent, ("code",)) or parent_id
            parent_status = _find_column(parent, ("status",))
            return MissingChildFlow(
                parent_table=parent,
                child_table=child,
                parent_id=parent_id,
                parent_label=parent_label,
                parent_status=parent_status,
                child_id=child_id,
                child_fk_to_parent=child_fk,
                child_label=child_label,
            )
    return None


def _infer_duplicate_child_flow(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> DuplicateChildFlow | None:
    question_text = " ".join(entities.business_keywords or [])
    problem = parse_problem_phrase(question_text)
    parsed_terms = set(problem.target_terms)
    terms = parsed_terms or _duplicate_target_terms(entities)
    key_value = next((entity.value for entity in entities.entities if entity.entity_type in {"business_key", "exact_id_or_code"}), None)
    resolved_child = resolve_table_from_terms(list(terms), metadata)
    child_candidates = sorted(
        metadata.tables,
        key=lambda table: (
            10 if resolved_child and table.name == resolved_child.name else 0,
            sum(
                1
                for term in terms
                if (term.rstrip("s") in table.name.lower() or term in table.name.lower())
            ),
        ),
        reverse=True,
    )
    for child in child_candidates:
        if not terms_match_table(list(terms), child) and not any(term.rstrip("s") in child.name.lower() or term in child.name.lower() for term in terms):
            continue
        child_label = _find_column(child, ("number",)) or _find_column(child, ("name",)) or _find_column(child, ("code",))
        child_status = _find_column(child, ("status",)) or _find_column(child, ("state",))
        for fk in child.foreign_keys or []:
            parent_name = str(fk.get("referred_table") or "")
            parent_cols = fk.get("referred_columns") or []
            child_cols = fk.get("columns") or fk.get("constrained_columns") or []
            parent = next((table for table in metadata.tables if table.name.lower() == parent_name.lower()), None)
            if not parent or not parent_cols or not child_cols:
                continue
            if problem.parent_terms and not terms_match_table(problem.parent_terms, parent):
                continue
            parent_label = _find_column(parent, ("number",)) or _find_column(parent, ("name",)) or _find_column(parent, ("code",)) or str(parent_cols[0])
            return DuplicateChildFlow(
                parent_table=parent,
                child_table=child,
                parent_id=str(parent_cols[0]),
                parent_label=parent_label,
                child_fk_to_parent=str(child_cols[0]),
                child_label=child_label,
                child_status=child_status,
                parent_key_value=key_value,
            )
    return None


def _missing_child_candidate_query(flow: MissingChildFlow) -> str:
    status_select = f"p.{flow.parent_status} AS parent_status," if flow.parent_status else "NULL AS parent_status,"
    child_label_select = f"c.{flow.child_label} AS child_reference," if flow.child_label else "NULL AS child_reference,"
    return f"""
SELECT
    p.{flow.parent_label} AS parent_reference,
    {status_select}
    {child_label_select}
    CASE
        WHEN c.{flow.child_id} IS NULL THEN 'MISSING_RELATED_RECORD'
        ELSE 'OK'
    END AS issue_type
FROM {flow.parent_table.name} p
LEFT JOIN {flow.child_table.name} c ON c.{flow.child_fk_to_parent} = p.{flow.parent_id}
WHERE c.{flow.child_id} IS NULL
ORDER BY p.{flow.parent_label}
""".strip()


def _missing_child_summary_query(flow: MissingChildFlow) -> str:
    return f"""
SELECT
    issue_type,
    COUNT(*) AS issue_count,
    MIN(parent_reference) AS example_parent
FROM (
    SELECT
        p.{flow.parent_label} AS parent_reference,
        CASE
            WHEN c.{flow.child_id} IS NULL THEN 'MISSING_RELATED_RECORD'
            ELSE 'OK'
        END AS issue_type
    FROM {flow.parent_table.name} p
    LEFT JOIN {flow.child_table.name} c ON c.{flow.child_fk_to_parent} = p.{flow.parent_id}
    WHERE c.{flow.child_id} IS NULL
) missing_related_candidates
GROUP BY issue_type
ORDER BY issue_count DESC
""".strip()


def _duplicate_child_query(flow: DuplicateChildFlow) -> str:
    return _duplicate_child_query_for_engine(flow, None)


def _duplicate_child_query_for_engine(flow: DuplicateChildFlow, engine_type: str | None) -> str:
    child_name = flow.child_table.name.rstrip("s")
    count_alias = f"{child_name}_count" if flow.child_status else f"duplicate_{child_name}_count"
    records_alias = f"{child_name}_numbers" if flow.child_label and "number" in flow.child_label.lower() else f"{child_name}_records"
    child_label_expr = (
        f"{_string_aggregate(f'c.{flow.child_label}', engine_type, f'c.{flow.child_label}')} AS {records_alias}"
        if flow.child_label
        else f"COUNT(*) AS {records_alias}"
    )
    status_expr = f",\n    {_string_aggregate(f'c.{flow.child_status}', engine_type, f'c.{flow.child_status}', distinct=True)} AS child_statuses" if flow.child_status else ""
    parent_filter = ""
    if flow.parent_key_value:
        escaped = flow.parent_key_value.replace("'", "''")
        parent_filter = f"\nWHERE p.{flow.parent_label} = '{escaped}'"
    return f"""
SELECT
    p.{flow.parent_label} AS parent_reference,
    COUNT(*) AS {count_alias},
    {child_label_expr}{status_expr}
FROM {flow.parent_table.name} p
JOIN {flow.child_table.name} c ON c.{flow.child_fk_to_parent} = p.{flow.parent_id}{parent_filter}
GROUP BY p.{flow.parent_label}
HAVING COUNT(*) > 1
""".strip()


def plan_safe_queries(intent: InvestigationIntent, metadata: MetadataSearchResult, entities: EntityExtractionResult) -> list[PlannedQuery]:
    planned: list[PlannedQuery] = []
    missing_child_flow = _infer_missing_child_flow(metadata, entities) if intent == InvestigationIntent.MISSING_DATA else None
    duplicate_child_flow = _infer_duplicate_child_flow(metadata, entities) if intent == InvestigationIntent.DUPLICATE_DATA else None
    if duplicate_child_flow:
        planned.append(
                PlannedQuery(
                    purpose=f"Find duplicate {duplicate_child_flow.child_table.name} per {duplicate_child_flow.parent_table.name}",
                    sql=_duplicate_child_query_for_engine(duplicate_child_flow, metadata.engine_type),
                )
        )
    if missing_child_flow:
        planned.extend(
            [
                PlannedQuery(
                    purpose="Confirmed Missing Related Record Candidates",
                    sql=_missing_child_candidate_query(missing_child_flow),
                ),
                PlannedQuery(
                    purpose="Missing Related Record Summary by Issue Type",
                    sql=_missing_child_summary_query(missing_child_flow),
                ),
            ]
        )
    for table in metadata.tables[:5]:
        where_clause = _where_for_table(table, entities, metadata.engine_type)
        columns = ", ".join(table.columns[:8]) if table.columns else "*"
        planned.append(PlannedQuery(purpose=f"Inspect relevant rows in {table.name}", sql=f"SELECT {columns} FROM {table.name}{where_clause}"))
    if intent == InvestigationIntent.PERFORMANCE_INVESTIGATION and metadata.tables:
        table = metadata.tables[0]
        columns = table.columns
        if columns:
            planned.append(PlannedQuery(purpose=f"Review execution plan for {table.name}", sql=f"EXPLAIN SELECT {', '.join(columns[:4])} FROM {table.name}"))
    if intent == InvestigationIntent.DUPLICATE_DATA:
        for table in metadata.tables[:3]:
            unique_cols = [
                column
                for index in table.indexes or []
                if index.get("unique")
                for column in index.get("columns", [])
                if column in table.columns
            ]
            natural_key_cols = [
                col
                for col in table.columns
                if re.search(r"(_number|_code|_ref|_key)$", col.lower())
            ]
            candidate_cols = list(dict.fromkeys([*unique_cols, *natural_key_cols]))
            if candidate_cols:
                col = candidate_cols[0]
                planned.append(PlannedQuery(purpose=f"Find duplicate business keys in {table.name}", sql=f"SELECT {col}, COUNT(*) AS duplicate_count FROM {table.name} GROUP BY {col} HAVING COUNT(*) > 1"))
    safe: list[PlannedQuery] = []
    for query in planned:
        sql = ensure_limit(query.sql)
        validate_read_only_sql(sql)
        safe.append(PlannedQuery(query.purpose, sql, query.risk))
    return safe[:8]


def _cast_to_text(expression: str, engine_type: str | None) -> str:
    engine = (engine_type or "").lower()
    if engine == "sql_server":
        return f"CAST({expression} AS NVARCHAR(MAX))"
    if engine == "postgresql":
        return f"CAST({expression} AS TEXT)"
    if engine == "sqlite":
        return f"CAST({expression} AS TEXT)"
    if engine == "oracle":
        return f"TO_CHAR({expression})"
    return f"CAST({expression} AS CHAR)"


def _string_aggregate(expression: str, engine_type: str | None, order_by: str | None = None, distinct: bool = False) -> str:
    engine = (engine_type or "").lower()
    value = _cast_to_text(expression, engine_type)
    if distinct:
        value = f"DISTINCT {value}"
    if engine == "postgresql":
        order = f" ORDER BY {order_by}" if order_by else ""
        return f"STRING_AGG({value}, ','{order})"
    if engine == "sql_server":
        order = f" WITHIN GROUP (ORDER BY {order_by})" if order_by else ""
        distinct_note = value.replace("DISTINCT ", "")
        return f"STRING_AGG({distinct_note}, ','){order}"
    if engine == "sqlite":
        return f"GROUP_CONCAT({value}, ',')"
    if engine == "oracle":
        order = order_by or expression
        distinct_prefix = "DISTINCT " if distinct else ""
        return f"LISTAGG({distinct_prefix}{expression}, ',') WITHIN GROUP (ORDER BY {order})"
    order = f" ORDER BY {order_by}" if order_by else ""
    return f"GROUP_CONCAT({value}{order})"
