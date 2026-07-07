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
class ProductionReadSafetyResult:
    sql: str
    changed: bool = False
    reason: str = ""


class ProductionReadSafetyValidator:
    """
    Owner: Mukesh Dabi
    Purpose:
        Applies production-read safeguards after SQL has passed the basic read-only validator.

    Input:
        Candidate read-only SQL, row estimates, engine type, max-row policy, and full-scan configuration.

    Output:
        ProductionReadSafetyResult with original or row-limited SQL plus a safety note.

    Called by:
        Evidence Collector before executing planned investigation SQL.

    Flow:
        Safe SQL Planner -> validate_read_only_sql -> ProductionReadSafetyValidator -> read-only connector.

    Safety:
        Rejects unrestricted scans unless explicitly allowed or safely limited; never permits write commands.
    """

    def __init__(
        self,
        *,
        max_rows: int = 100,
        allow_full_table_scan: bool = False,
        row_estimates: dict[str, int] | None = None,
        engine_type: str | None = None,
    ) -> None:
        self.max_rows = max_rows
        self.allow_full_table_scan = allow_full_table_scan
        self.row_estimates = {key.lower(): value for key, value in (row_estimates or {}).items()}
        self.engine_type = (engine_type or "").lower()

    def validate(self, sql: str) -> ProductionReadSafetyResult:
        stripped = sql.strip().rstrip(";")
        normalized = _sql_without_literals_and_comments(stripped)
        command = _first_sql_word(normalized)
        if command in {"show", "describe", "desc"}:
            return ProductionReadSafetyResult(stripped)
        if command == "explain":
            return ProductionReadSafetyResult(stripped)
        if command != "select":
            return ProductionReadSafetyResult(stripped)
        table_name = _first_from_table(normalized)
        if table_name and _is_allowed_metadata_table(table_name):
            return ProductionReadSafetyResult(stripped)
        if _is_count_discovery(normalized):
            return ProductionReadSafetyResult(stripped)
        if _has_where_clause(normalized) or _has_limit_clause(normalized):
            return ProductionReadSafetyResult(stripped)
        if self.allow_full_table_scan:
            return ProductionReadSafetyResult(stripped)
        if not table_name:
            return ProductionReadSafetyResult(stripped)
        if self._can_auto_limit(table_name):
            return ProductionReadSafetyResult(
                _add_exploration_limit(stripped, self.max_rows, self.engine_type),
                changed=True,
                reason="Production scan protection: added investigation row limit.",
            )
        raise ValueError("Production scan protection rejected unrestricted table scan")

    def _can_auto_limit(self, table_name: str) -> bool:
        normalized_table = _unquote_identifier(table_name).lower().split(".")[-1]
        estimate = self.row_estimates.get(normalized_table) or self.row_estimates.get(_unquote_identifier(table_name).lower())
        if estimate is not None:
            return estimate <= self.max_rows
        return bool(re.search(r"(^|_)(lookup|reference|ref|status|type|category|code)(_|s?$)", normalized_table))


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


_ALLOWED_COMMANDS = {"select", "show", "describe", "desc", "explain"}
_BLOCKED_COMMANDS = {
    "alter",
    "call",
    "create",
    "delete",
    "drop",
    "exec",
    "execute",
    "grant",
    "insert",
    "merge",
    "replace",
    "revoke",
    "truncate",
    "update",
}
_WRITE_LOCK_CLAUSES = re.compile(r"\b(for\s+update|lock\s+in\s+share\s+mode)\b", re.I)


def _sql_without_literals_and_comments(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    without_line_comments = re.sub(r"--[^\r\n]*", " ", without_block_comments)
    without_single_quotes = re.sub(r"'(?:''|[^'])*'", "''", without_line_comments)
    without_double_quotes = re.sub(r'"(?:""|[^"])*"', '""', without_single_quotes)
    without_backticks = re.sub(r"`(?:``|[^`])*`", "``", without_double_quotes)
    return without_backticks


def _first_sql_word(sql: str) -> str:
    match = re.match(r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\b", sql)
    return match.group(1).lower() if match else ""


def _unquote_identifier(value: str) -> str:
    return value.strip().strip("`[]\"")


def _first_from_table(sql: str) -> str | None:
    match = re.search(r"\bfrom\s+([`\"\[\]\w.]+)", sql, re.I)
    return match.group(1) if match else None


def _is_allowed_metadata_table(table_name: str) -> bool:
    normalized = _unquote_identifier(table_name).lower()
    return normalized in {
        "information_schema.tables",
        "information_schema.columns",
        "information_schema.routines",
    }


def _is_count_discovery(sql: str) -> bool:
    return bool(re.match(r"\s*select\s+count\s*\(\s*\*\s*\)(\s+as\s+\w+)?\s+from\s+[`\"\[\]\w.]+\s*$", sql, re.I))


def _has_where_clause(sql: str) -> bool:
    return bool(re.search(r"\bwhere\b", sql, re.I))


def _has_limit_clause(sql: str) -> bool:
    return bool(re.search(r"\blimit\s+\d+\b", sql, re.I) or re.match(r"\s*select\s+top\s+\d+\b", sql, re.I))


def _add_exploration_limit(sql: str, limit: int, engine_type: str | None = None) -> str:
    if _has_limit_clause(sql):
        return sql
    if (engine_type or "").lower() == "sql_server":
        return re.sub(r"^\s*select\b", f"SELECT TOP {limit}", sql, count=1, flags=re.I)
    return f"{sql} LIMIT {limit}"


def validate_read_only_sql(sql: str) -> None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Enforces the core SQL safety boundary for investigations and verification checks.

    Input:
        Candidate SQL text.

    Output:
        None when SQL is safe; raises ValueError when unsafe.

    Called by:
        Safe SQL Planner, Evidence Collector, Evidence Verification Agent, and report/proof SQL validation paths.

    Flow:
        Generated SQL -> SafeSQLValidator -> optional production read validator -> connector execution.

    Safety:
        Allows only SELECT, SHOW, DESCRIBE, DESC, and EXPLAIN SELECT. Blocks INSERT, UPDATE, DELETE, ALTER,
        DROP, TRUNCATE, EXEC, CALL, locks, and multi-statement SQL.
    """

    stripped = sql.strip().rstrip(";")
    normalized = _sql_without_literals_and_comments(stripped)
    command = _first_sql_word(normalized)
    if command in _BLOCKED_COMMANDS:
        raise ValueError("Unsafe SQL command rejected")
    if command not in _ALLOWED_COMMANDS:
        raise ValueError("Only SELECT, SHOW, DESCRIBE, and EXPLAIN statements are allowed")
    if ";" in normalized:
        raise ValueError("Multiple SQL statements are not allowed")
    if command == "explain":
        explain_target = _first_sql_word(re.sub(r"^\s*explain\b", "", normalized, count=1, flags=re.I))
        if explain_target != "select":
            raise ValueError("Only EXPLAIN SELECT statements are allowed")
    if _WRITE_LOCK_CLAUSES.search(normalized):
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


def _status_literal_from_terms(terms: list[str], table: TableMetadata) -> str | None:
    table_tokens = set(re.split(r"[_\-\s]+", table.name.lower()))
    for column in table.columns:
        table_tokens.update(part for part in re.split(r"[_\-\s]+", column.lower()) if part)
    status_terms = [
        term
        for term in terms
        if term not in table_tokens
        and term not in {"process", "processing", "job", "batch", "query", "report"}
    ]
    if not status_terms:
        return None
    return "_".join(status_terms[:3]).upper()


def _performance_target_table(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> tuple[TableMetadata | None, list[str]]:
    question_text = " ".join(entities.business_keywords or [])
    problem = parse_problem_phrase(question_text)
    terms = problem.target_terms or [
        term
        for term in (entities.business_keywords or [])
        if term not in {"analyze", "explain", "indexes", "index", "rows", "scans", "recommend", "optimization"}
    ]
    resolved = resolve_table_from_terms(terms, metadata)
    if resolved:
        return resolved, terms
    if metadata.tables:
        return metadata.tables[0], terms
    return None, terms


def _index_inspection_query(table: TableMetadata, engine_type: str | None) -> str:
    engine = (engine_type or "").lower()
    escaped = table.name.replace("'", "''")
    if engine == "mysql":
        return f"SHOW INDEX FROM {table.name}"
    if engine == "postgresql":
        return (
            "SELECT indexname, indexdef "
            "FROM pg_indexes "
            f"WHERE tablename = '{escaped}' "
            "ORDER BY indexname"
        )
    if engine == "sql_server":
        return f"""
SELECT
    i.name AS index_name,
    i.is_unique,
    c.name AS column_name,
    ic.key_ordinal
FROM sys.indexes i
JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE i.object_id = OBJECT_ID('{escaped}')
ORDER BY i.name, ic.key_ordinal
""".strip()
    return f"SELECT * FROM {table.name} WHERE 1 = 0"


def _performance_queries(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> list[PlannedQuery]:
    table, terms = _performance_target_table(metadata, entities)
    if table is None:
        return []
    status_col = _find_column(table, ("status",)) or _find_column(table, ("state",))
    time_col = (
        _find_column(table, ("time",), ("created", "updated", "checkout", "processed"))
        or _find_column(table, ("date",), ("created", "updated", "processed"))
        or _find_column(table, ("at",), ("created", "updated", "processed"))
    )
    columns = ", ".join(table.columns[:6]) if table.columns else "*"
    filters: list[str] = []
    status_literal = _status_literal_from_terms(terms, table)
    if status_col and status_literal:
        filters.append(f"{status_col} = '{status_literal}'")
    where_clause = " WHERE " + " AND ".join(filters) if filters else ""
    order_clause = f" ORDER BY {time_col}" if time_col else ""
    queries = [
        PlannedQuery(
            purpose=f"Review indexes on performance target table {table.name}",
            sql=_index_inspection_query(table, metadata.engine_type),
        ),
    ]
    if status_col:
        queries.append(
            PlannedQuery(
                purpose=f"Count rows by status/state in {table.name}",
                sql=f"SELECT {status_col}, COUNT(*) AS row_count FROM {table.name} GROUP BY {status_col} ORDER BY row_count DESC",
            )
        )
    queries.append(
        PlannedQuery(
            purpose=f"EXPLAIN performance target query for {table.name}",
            sql=f"EXPLAIN SELECT {columns} FROM {table.name}{where_clause}{order_clause}",
        )
    )
    if time_col:
        time_filters = [*filters, f"{time_col} IS NOT NULL"]
        queries.append(
            PlannedQuery(
                purpose=f"Inspect time distribution for {table.name}",
                sql=(
                    f"SELECT MIN({time_col}) AS oldest_value, MAX({time_col}) AS newest_value, "
                    f"COUNT(*) AS row_count FROM {table.name}"
                    + (" WHERE " + " AND ".join(time_filters) if time_filters else "")
                ),
            )
        )
    return queries


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


def _duplicate_parent_lookup_query(flow: DuplicateChildFlow) -> str:
    escaped = (flow.parent_key_value or "").replace("'", "''")
    child_count_alias = f"{flow.child_table.name.rstrip('s')}_count"
    parent_filter = f"\nWHERE p.{flow.parent_label} = '{escaped}'" if flow.parent_key_value else ""
    return f"""
SELECT
    p.{flow.parent_id} AS parent_id,
    p.{flow.parent_label} AS parent_reference,
    COUNT(c.{flow.child_fk_to_parent}) AS {child_count_alias}
FROM {flow.parent_table.name} p
LEFT JOIN {flow.child_table.name} c ON c.{flow.child_fk_to_parent} = p.{flow.parent_id}{parent_filter}
GROUP BY p.{flow.parent_id}, p.{flow.parent_label}
""".strip()


def _duplicate_child_detail_query_for_engine(flow: DuplicateChildFlow, engine_type: str | None) -> str:
    child_columns = [
        column
        for column in flow.child_table.columns
        if column in {
            flow.child_fk_to_parent,
            flow.child_label,
            flow.child_status,
        }
        or column.lower().endswith(("_id", "_number", "_code", "_status", "_state"))
        or column.lower() in {"retry_source", "created_at", "updated_at", "ordered_at"}
    ][:10]
    if not child_columns:
        child_columns = flow.child_table.columns[:8]
    child_select = ",\n    ".join(f"c.{column} AS child_{column}" for column in child_columns)
    parent_filter = ""
    if flow.parent_key_value:
        escaped = flow.parent_key_value.replace("'", "''")
        parent_filter = f"\nWHERE p.{flow.parent_label} = '{escaped}'"
    return f"""
SELECT
    p.{flow.parent_label} AS parent_reference,
    {child_select}
FROM {flow.parent_table.name} p
JOIN {flow.child_table.name} c ON c.{flow.child_fk_to_parent} = p.{flow.parent_id}{parent_filter}
ORDER BY p.{flow.parent_label}{', c.' + flow.child_label if flow.child_label else ''}
""".strip()


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


def _duplicate_like_investigation(intent: InvestigationIntent, entities: EntityExtractionResult) -> bool:
    if intent == InvestigationIntent.DUPLICATE_DATA:
        return True
    if intent != InvestigationIntent.PRODUCTION_INVESTIGATION:
        return False
    text = " ".join([entities.suspected_issue or "", *(entities.business_keywords or [])]).lower()
    return any(term in text for term in ("duplicate", "duplicated", "two", "multiple", "double", "created twice"))


def plan_safe_queries(intent: InvestigationIntent, metadata: MetadataSearchResult, entities: EntityExtractionResult) -> list[PlannedQuery]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Builds safe read-only SQL evidence queries for a database-generic investigation.

    Input:
        Investigation intent, extracted entities, discovered metadata, relationships, and engine type.

    Output:
        PlannedQuery list containing read-only SQL and evidence purpose labels.

    Called by:
        Main /chat/ask orchestration before evidence collection.

    Flow:
        User question -> Intent Agent -> Metadata Discovery -> Safe SQL Planner -> SQL Validator -> Evidence Collector.

    Safety:
        This planner must never emit INSERT, UPDATE, DELETE, ALTER, DROP, CALL, EXEC, or stored procedure execution.
        Unsafe candidates are discarded before returning the plan.
    """

    planned: list[PlannedQuery] = []
    missing_child_flow = _infer_missing_child_flow(metadata, entities) if intent == InvestigationIntent.MISSING_DATA else None
    duplicate_child_flow = _infer_duplicate_child_flow(metadata, entities) if _duplicate_like_investigation(intent, entities) else None
    if duplicate_child_flow:
        planned.extend(
            [
                PlannedQuery(
                    purpose=f"Resolve parent business key in {duplicate_child_flow.parent_table.name}",
                    sql=_duplicate_parent_lookup_query(duplicate_child_flow),
                ),
                PlannedQuery(
                    purpose=f"Find duplicate {duplicate_child_flow.child_table.name} per {duplicate_child_flow.parent_table.name}",
                    sql=_duplicate_child_query_for_engine(duplicate_child_flow, metadata.engine_type),
                ),
                PlannedQuery(
                    purpose=f"Inspect {duplicate_child_flow.child_table.name} rows through {duplicate_child_flow.parent_table.name} key",
                    sql=_duplicate_child_detail_query_for_engine(duplicate_child_flow, metadata.engine_type),
                ),
            ]
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
    if intent == InvestigationIntent.PERFORMANCE_INVESTIGATION:
        planned.extend(_performance_queries(metadata, entities))
    targeted_duplicate_tables = (
        {duplicate_child_flow.parent_table.name.lower(), duplicate_child_flow.child_table.name.lower()}
        if duplicate_child_flow
        else set()
    )
    for table in metadata.tables[:5]:
        if table.name.lower() in targeted_duplicate_tables:
            continue
        where_clause = _where_for_table(table, entities, metadata.engine_type)
        columns = ", ".join(table.columns[:8]) if table.columns else "*"
        planned.append(PlannedQuery(purpose=f"Inspect relevant rows in {table.name}", sql=f"SELECT {columns} FROM {table.name}{where_clause}"))
    if _duplicate_like_investigation(intent, entities):
        for table in metadata.tables[:3]:
            if table.name.lower() in targeted_duplicate_tables:
                continue
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
        try:
            validate_read_only_sql(sql)
        except ValueError:
            continue
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
