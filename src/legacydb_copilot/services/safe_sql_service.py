from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.diagnostic_object_service import is_diagnostic_object
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.problem_phrase_service import parse_problem_phrase, resolve_table_from_terms, terms_match_table
from legacydb_copilot.services.transfer_identifier_normalization import typed_transfer_identifier


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlannedQuery:
    purpose: str
    sql: str
    risk: str = "Read-only"
    query_id: str = ""


def _record_plan_event(events: list[dict[str, Any]] | None, *, query: PlannedQuery, status: str, reason: str = "") -> None:
    if events is None:
        return
    events.append(
        {
            "query_id": query.query_id,
            "purpose": query.purpose,
            "status": status,
            "reason": reason,
            "sql": query.sql,
        }
    )


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
        """
        Owner: Mukesh Dabi
        Purpose:
            Internal helper for init within safe_sql_service.py.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Internal callers in safe_sql_service.py.
        
        Where it fits in the flow:
            Intent and metadata -> safe SQL planner -> validator -> evidence collector.
        
        Safety considerations:
            Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
        """
        self.max_rows = max_rows
        self.allow_full_table_scan = allow_full_table_scan
        self.row_estimates = {key.lower(): value for key, value in (row_estimates or {}).items()}
        self.engine_type = (engine_type or "").lower()

    def validate(self, sql: str) -> ProductionReadSafetyResult:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles validate within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Investigation, reporting, verification, or knowledge workflows as needed.
        
        Where it fits in the flow:
            Intent and metadata -> safe SQL planner -> validator -> evidence collector.
        
        Safety considerations:
            Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
        """
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
        """
        Owner: Mukesh Dabi
        Purpose:
            Internal helper for can auto limit within safe_sql_service.py.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Internal callers in safe_sql_service.py.
        
        Where it fits in the flow:
            Intent and metadata -> safe SQL planner -> validator -> evidence collector.
        
        Safety considerations:
            Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
        """
        qualified_table = _unquote_identifier(table_name).lower()
        normalized_table = qualified_table.split(".")[-1]
        estimate = self.row_estimates.get(qualified_table)
        if estimate is None:
            estimate = self.row_estimates.get(normalized_table)
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
    parent_key_value: str | None = None
    expected_child_terms: tuple[str, ...] = ()
    engine_type: str | None = None


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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for sql without literals and comments within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    without_line_comments = re.sub(r"--[^\r\n]*", " ", without_block_comments)
    without_single_quotes = re.sub(r"'(?:''|[^'])*'", "''", without_line_comments)
    without_double_quotes = re.sub(r'"(?:""|[^"])*"', '""', without_single_quotes)
    without_backticks = re.sub(r"`(?:``|[^`])*`", "``", without_double_quotes)
    return without_backticks


def _first_sql_word(sql: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for first sql word within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    match = re.match(r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\b", sql)
    return match.group(1).lower() if match else ""


def _unquote_identifier(value: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for unquote identifier within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    return value.strip().strip("`[]\"")


def _first_from_table(sql: str) -> str | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for first from table within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    match = re.search(r"\bfrom\s+([`\"\[\]\w.]+)", sql, re.I)
    return match.group(1) if match else None


def _is_allowed_metadata_table(table_name: str) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for is allowed metadata table within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    normalized = _unquote_identifier(table_name).lower()
    return normalized in {
        "information_schema.tables",
        "information_schema.columns",
        "information_schema.routines",
    }


def _is_count_discovery(sql: str) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for is count discovery within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    return bool(re.match(r"\s*select\s+count\s*\(\s*\*\s*\)(\s+as\s+\w+)?\s+from\s+[`\"\[\]\w.]+\s*$", sql, re.I))


def _has_where_clause(sql: str) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for has where clause within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    return bool(re.search(r"\bwhere\b", sql, re.I))


def _has_limit_clause(sql: str) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for has limit clause within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    return bool(re.search(r"\blimit\s+\d+\b", sql, re.I) or re.match(r"\s*select\s+top\s+\d+\b", sql, re.I))


def _add_exploration_limit(sql: str, limit: int, engine_type: str | None = None) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for add exploration limit within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles ensure limit within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    stripped = sql.strip().rstrip(";")
    return stripped


def _where_for_table(table: TableMetadata, entities: EntityExtractionResult, engine_type: str | None = None) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for where for table within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    filters: list[str] = []
    business_values = [
        entity.value
        for entity in entities.entities
        if entity.entity_type in {"business_key", "exact_id_or_code", "business_identifier"}
    ]
    for value in business_values:
        escaped = value.replace("'", "''")
        column_filters = []
        for column in table.columns:
            column_l = column.lower()
            if (
                column_l == "id"
                or column_l.endswith("_id")
                or any(term in column_l for term in ("number", "code", "key", "reference"))
            ):
                column_filters.append(f"{_cast_to_text(column, engine_type)} = '{escaped}'")
        if column_filters:
            filters.append("(" + " OR ".join(column_filters[:6]) + ")")
    return " WHERE " + " OR ".join(filters) if filters else ""


def _find_column(table: TableMetadata, required_terms: tuple[str, ...], optional_terms: tuple[str, ...] = ()) -> str | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for find column within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for missing target terms within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    stop = {"missing", "records", "record", "where", "with", "without", "find", "show", "group", "root", "cause", "caused"}
    terms = {term.lower() for term in (entities.business_keywords or []) if len(term) >= 3 and term.lower() not in stop}
    for entity in entities.entities:
        terms.update(part.lower() for part in re.split(r"[^a-zA-Z0-9]+", entity.value) if len(part) >= 3)
    return terms


def _duplicate_target_terms(entities: EntityExtractionResult) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate target terms within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    stop = {"duplicate", "duplicates", "multiple", "active", "open", "valid", "created", "create", "where", "with", "why", "did", "two", "processed", "twice"}
    terms = {term.lower() for term in (entities.business_keywords or []) if len(term) >= 3 and term.lower() not in stop}
    return terms


def _business_key_values(entities: EntityExtractionResult) -> list[str]:
    return [
        entity.value
        for entity in entities.entities
        if entity.entity_type in {"business_key", "exact_id_or_code", "business_identifier"}
    ]


def _typed_transfer_identifier(entities: EntityExtractionResult) -> str | None:
    return typed_transfer_identifier(entities)


def _looks_like_transfer_table(table: TableMetadata) -> bool:
    lowered = table.name.lower()
    leaf = lowered.split(".")[-1]
    return leaf == "transfers" or leaf.endswith("_transfers") or "transfer" in leaf


def _exact_business_key_column(table: TableMetadata) -> str | None:
    preferred = [
        "BusinessKey",
        "business_key",
        "transfer_number",
        "transfer_code",
        "reference_key",
    ]
    by_fold = {column.casefold(): column for column in table.columns}
    for name in preferred:
        match = by_fold.get(name.casefold())
        if match:
            return match
    for column in table.columns:
        lowered = column.lower()
        if "transfer" in lowered and any(marker in lowered for marker in ("number", "code", "key", "reference")):
            return column
    for column in _natural_key_columns(table):
        lowered = column.lower()
        if all(marker not in lowered for marker in ("status", "state", "message", "detail", "description", "reason")):
            return column
    return None


def _transfer_primary_query(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> PlannedQuery | None:
    transfer_id = _typed_transfer_identifier(entities)
    if not transfer_id:
        return None
    transfer_tables = [table for table in metadata.tables if _looks_like_transfer_table(table)]
    if not transfer_tables:
        return None
    transfer_table = sorted(transfer_tables, key=lambda item: (item.score, _header_rank(item), len(item.name)), reverse=True)[0]
    key_column = _exact_business_key_column(transfer_table)
    if not key_column:
        return None
    escaped = transfer_id.replace("'", "''")
    columns = ", ".join(transfer_table.columns[:8]) if transfer_table.columns else "*"
    return PlannedQuery(
        purpose=f"Prove requested entity exists in {transfer_table.name}",
        sql=f"SELECT {columns} FROM {transfer_table.name} WHERE {_cast_to_text(key_column, metadata.engine_type)} = '{escaped}'",
    )


def _supporting_transfer_relationship_queries(
    metadata: MetadataSearchResult,
    entities: EntityExtractionResult,
    debug_events: list[dict[str, Any]] | None = None,
) -> list[PlannedQuery]:
    transfer_id = _typed_transfer_identifier(entities)
    if not transfer_id:
        return []
    transfer_tables = [table for table in metadata.tables if _looks_like_transfer_table(table)]
    if not transfer_tables:
        return []
    transfer_table = sorted(transfer_tables, key=lambda item: (item.score, _header_rank(item), len(item.name)), reverse=True)[0]
    transfer_key = _exact_business_key_column(transfer_table)
    if not transfer_key:
        return []
    escaped = transfer_id.replace("'", "''")
    families = ("account", "transaction", "fraud", "audit", "payment", "settlement", "integration_message")
    supporting: list[PlannedQuery] = []

    def _qualified_columns(columns: list[str], alias: str, prefix: str, limit: int = 8) -> list[str]:
        selected = columns[:limit]
        return [f"{alias}.{column} AS {prefix}{column}" for column in selected]

    for table in metadata.tables:
        if table.name == transfer_table.name:
            continue
        lowered = table.name.lower()
        if not any(marker in lowered for marker in families):
            continue
        role = "supporting"
        if "integration_message" in lowered or lowered.endswith(".integration_messages"):
            role = "diagnostic support"
        joined = False
        for fk in table.foreign_keys or []:
            referred = str(fk.get("referred_table") or "").casefold()
            if referred != transfer_table.name.casefold():
                continue
            fk_columns = [column for column in fk.get("columns", []) if column in table.columns]
            ref_columns = [column for column in fk.get("referred_columns", []) if column in transfer_table.columns]
            if not fk_columns or not ref_columns:
                continue
            child_col = fk_columns[0]
            parent_col = ref_columns[0]
            transfer_projection = _qualified_columns(transfer_table.columns, "t", "Transfer") if transfer_table.columns else ["t.*"]
            related_projection = _qualified_columns(table.columns, "s", "Related") if table.columns else ["s.*"]
            projection = ", ".join([*transfer_projection, *related_projection])
            supporting.append(
                PlannedQuery(
                    purpose=f"Inspect {role} relationship evidence in {table.name}",
                    sql=(
                        f"SELECT {projection} FROM {transfer_table.name} t "
                        f"JOIN {table.name} s ON s.{child_col} = t.{parent_col} "
                        f"WHERE {_cast_to_text('t.' + transfer_key, metadata.engine_type)} = '{escaped}'"
                    ),
                )
            )
            joined = True
            break
        if joined:
            continue
        for fk in transfer_table.foreign_keys or []:
            referred = str(fk.get("referred_table") or "").casefold()
            if referred != table.name.casefold():
                continue
            fk_columns = [column for column in fk.get("columns", []) if column in transfer_table.columns]
            ref_columns = [column for column in fk.get("referred_columns", []) if column in table.columns]
            if not fk_columns or not ref_columns:
                continue
            transfer_fk = fk_columns[0]
            related_pk = ref_columns[0]
            transfer_projection = _qualified_columns(transfer_table.columns, "t", "Transfer") if transfer_table.columns else ["t.*"]
            related_projection = _qualified_columns(table.columns, "s", "Related") if table.columns else ["s.*"]
            projection = ", ".join([*transfer_projection, *related_projection])
            supporting.append(
                PlannedQuery(
                    purpose=f"Inspect {role} relationship evidence in {table.name}",
                    sql=(
                        f"SELECT {projection} FROM {transfer_table.name} t "
                        f"JOIN {table.name} s ON s.{related_pk} = t.{transfer_fk} "
                        f"WHERE {_cast_to_text('t.' + transfer_key, metadata.engine_type)} = '{escaped}'"
                    ),
                )
            )
            break
        if not joined:
            candidate = PlannedQuery(
                purpose=f"Inspect {role} relationship evidence in {table.name}",
                sql=f"SELECT * FROM {table.name}",
                query_id=f"REL-FILTER-{table.name}",
            )
            _record_plan_event(
                debug_events,
                query=candidate,
                status="rejected",
                reason="relationship_filtering:no_join_path_discovered",
            )
    return supporting[:8]


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


def _requested_column_concepts(entities: EntityExtractionResult) -> set[str]:
    stop = {"why", "root", "cause", "record", "records", "missing", "null", "issue", "failed", "generated"}
    concepts: set[str] = set()
    for entity in entities.entities:
        if entity.entity_type in {"possible_column", "possible_table_or_column"}:
            concepts.update(_identifier_parts(entity.value))
    for token in entities.business_keywords or []:
        concepts.update(_identifier_parts(token))
    return {concept for concept in concepts if concept not in stop}


def _reported_null_condition(entities: EntityExtractionResult) -> bool:
    text = " ".join([entities.suspected_issue or "", *(entities.business_keywords or [])]).lower()
    return any(term in text for term in ("null", "blank", "empty", "missing"))


def _condition_columns(table: TableMetadata, entities: EntityExtractionResult) -> list[str]:
    concepts = _requested_column_concepts(entities)
    matches: list[tuple[int, str]] = []
    for column in table.columns:
        parts = _identifier_parts(column)
        hits = parts & concepts
        if hits:
            matches.append((len(hits), column))
    matches.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return [column for _, column in matches[:3]]


def _entity_and_condition_queries(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> list[PlannedQuery]:
    key_values = _business_key_values(entities)
    if not key_values:
        return []
    planned: list[PlannedQuery] = []
    candidate_tables = list(metadata.tables[:3])
    if _typed_transfer_identifier(entities):
        candidate_tables.sort(
            key=lambda table: (
                not _looks_like_transfer_table(table),
                is_diagnostic_object(table.name),
                -table.score,
            )
        )
    for index, table in enumerate(candidate_tables):
        where_clause = _where_for_table(table, entities, metadata.engine_type)
        if where_clause:
            columns = ", ".join(table.columns[:8]) if table.columns else "*"
            purpose = (
                f"Prove requested entity exists in {table.name}"
                if index == 0
                else f"Inspect supporting rows in {table.name}"
            )
            planned.append(
                PlannedQuery(
                    purpose=purpose,
                    sql=f"SELECT {columns} FROM {table.name}{where_clause}",
                )
            )
        if not _reported_null_condition(entities):
            continue
        for column in _condition_columns(table, entities):
            filters = []
            if where_clause:
                filters.append(f"({where_clause.removeprefix(' WHERE ')})")
            filters.append(f"{column} IS NULL")
            planned.append(
                PlannedQuery(
                    purpose=f"Prove reported condition on {table.name}.{column}",
                    sql=f"SELECT {', '.join(dict.fromkeys([column, *table.columns[:7]]))} FROM {table.name} WHERE {' AND '.join(filters)}",
                )
            )
    return planned


def _natural_key_columns(table: TableMetadata) -> list[str]:
    priority = []
    for column in table.columns:
        lowered = column.lower()
        if lowered.endswith("_id") or lowered == "id" or column in (table.primary_key or []):
            continue
        if lowered == "reference_key":
            priority.append((0, column))
        elif lowered.endswith("_number"):
            priority.append((1, column))
        elif lowered.endswith("_code"):
            priority.append((2, column))
        elif lowered.endswith("_key") or lowered.endswith("_ref") or "reference" in lowered:
            priority.append((3, column))
    return [column for _, column in sorted(priority, key=lambda item: (item[0], item[1]))]


def _header_rank(table: TableMetadata) -> int:
    lowered = table.name.lower()
    if re.search(r"(^|_)(lines?|details?|history|audit|logs?|items?)$", lowered):
        return -5
    if any(token in lowered for token in ("_line", "_detail", "_history", "_audit", "_log")):
        return -4
    return 3


def _status_columns(table: TableMetadata) -> list[str]:
    return [column for column in table.columns if any(term in column.lower() for term in ("status", "state"))]


def _reported_stuck_status(entities: EntityExtractionResult) -> str | None:
    status_values = [
        entity.value
        for entity in entities.entities
        if entity.entity_type == "status_or_code"
    ]
    key_prefixes = {value.split("-", 1)[0] for value in _business_key_values(entities) if "-" in value}
    for value in status_values:
        if value not in key_prefixes:
            return value
    keywords = entities.business_keywords or []
    for index, token in enumerate(keywords):
        if token.lower() == "in" and index + 1 < len(keywords):
            candidate = keywords[index + 1]
            if candidate.isupper():
                return candidate
    return None


def _status_investigation_queries(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> list[PlannedQuery]:
    key_values = _business_key_values(entities)
    stuck_status = _reported_stuck_status(entities)
    candidates = [
        table
        for table in metadata.tables
        if _status_columns(table)
    ]
    if not candidates:
        return []
    table = sorted(candidates, key=lambda item: (item.score, _header_rank(item), len(item.name)), reverse=True)[0]
    status_col = _status_columns(table)[0]
    label = _natural_key_columns(table)[0] if _natural_key_columns(table) else table.columns[0]
    columns = [label, status_col]
    select_cols = ", ".join(dict.fromkeys([*columns, *table.columns[:4]]))
    filters = []
    for value in key_values:
        escaped = value.replace("'", "''")
        filters.append(f"{_cast_to_text(label, metadata.engine_type)} = '{escaped}'")
    where = f" WHERE {' OR '.join(filters)}" if filters else ""
    reported = f", '{stuck_status}' AS reported_stuck_status" if stuck_status else ""
    return [
        PlannedQuery(
            purpose=f"Confirm current status in {table.name}",
            sql=f"SELECT {select_cols}, {status_col} AS current_status{reported} FROM {table.name}{where}",
        )
    ]


def _analytical_summary_queries(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> list[PlannedQuery]:
    terms = set(entities.business_keywords or [])
    quality_terms = {"data", "quality", "rule", "rules", "result", "results", "failure", "failed", "failures"}
    terms.update(quality_terms if {"quality", "rules"} & terms else set())
    candidates = []
    for table in metadata.tables:
        haystack = " ".join([table.name, *table.columns]).lower()
        score = sum(1 for term in terms if term.lower() in haystack)
        if score:
            candidates.append((score + table.score, table))
    candidates.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    planned = []
    for _, table in candidates[:3]:
        status_col = _find_column(table, ("status",)) or _find_column(table, ("result",)) or _find_column(table, ("state",))
        rule_col = _find_column(table, ("rule", "code")) or _find_column(table, ("rule", "name")) or _find_column(table, ("name",)) or _find_column(table, ("code",))
        date_col = _find_column(table, ("date",)) or _find_column(table, ("created",)) or _find_column(table, ("run",))
        if status_col:
            group_cols = ", ".join(col for col in [rule_col, status_col] if col)
            where_parts = []
            if date_col:
                where_parts.append(f"{date_col} IS NOT NULL")
            if any(term in terms for term in ("failed", "failure", "failures")):
                where_parts.append(f"LOWER({_cast_to_text(status_col, metadata.engine_type)}) LIKE '%fail%'")
            where = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
            planned.append(
                PlannedQuery(
                    purpose=f"Summarize analytical results in {table.name}",
                    sql=f"SELECT {group_cols}, COUNT(*) AS result_count FROM {table.name}{where} GROUP BY {group_cols} ORDER BY result_count DESC",
                )
            )
        else:
            planned.append(
                PlannedQuery(
                    purpose=f"Count matching analytical rows in {table.name}",
                    sql=f"SELECT COUNT(*) AS result_count FROM {table.name}",
                )
            )
    return planned


def _status_literal_from_terms(terms: list[str], table: TableMetadata) -> str | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for status literal from terms within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for performance target table within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for index inspection query within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for performance queries within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for infer missing child flow within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    question_text = " ".join(entities.business_keywords or [])
    problem = parse_problem_phrase(question_text)
    parsed_terms = set(problem.target_terms)
    terms = parsed_terms or _missing_target_terms(entities)
    if not terms:
        return None
    resolved_child = resolve_table_from_terms(list(terms), metadata)
    relationships = _missing_relationship_candidates(metadata, problem.parent_terms, list(terms), resolved_child)
    for _, parent, child, parent_id, child_fk in relationships:
        child_id = _identity_column(child, avoid={child_fk})
        child_label = _find_column(child, ("number",)) or _find_column(child, ("name",)) or _find_column(child, ("code",))
        if not child_id:
            continue
        parent_label = (
            _find_column(parent, ("business", "key"))
            or _find_column(parent, ("number",))
            or _find_column(parent, ("name",))
            or _find_column(parent, ("code",))
            or parent_id
        )
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
            parent_key_value=next(
                (
                    entity.value
                    for entity in entities.entities
                    if entity.entity_type
                    in {"business_key", "business_identifier", "exact_id_or_code"}
                ),
                None,
            ),
            expected_child_terms=tuple(
                term.lower()
                for term in dict.fromkeys([*problem.target_terms, *problem.parent_terms])
                if len(term) >= 4
            ),
            engine_type=metadata.engine_type,
        )
    return None


def _missing_relationship_candidates(
    metadata: MetadataSearchResult,
    parent_terms: list[str],
    child_terms: list[str],
    resolved_child: TableMetadata | None,
) -> list[tuple[float, TableMetadata, TableMetadata, str, str]]:
    declared: list[tuple[float, TableMetadata, TableMetadata, str, str]] = []
    inferred: list[tuple[float, TableMetadata, TableMetadata, str, str]] = []
    table_lookup = {table.name.lower(): table for table in metadata.tables}
    for child in metadata.tables:
        for fk in child.foreign_keys or []:
            parent_name = str(fk.get("referred_table") or "")
            parent_cols = fk.get("referred_columns") or []
            child_cols = fk.get("columns") or fk.get("constrained_columns") or []
            parent = table_lookup.get(parent_name.lower())
            if not parent or not parent_cols or not child_cols:
                continue
            phrase_score = _relationship_phrase_score(parent, child, parent_terms, child_terms, resolved_child)
            if phrase_score > 0:
                declared.append((phrase_score + 100.0, parent, child, str(parent_cols[0]), str(child_cols[0])))
    if declared:
        declared.sort(key=lambda item: (item[0], item[2].score, item[1].score, item[2].name), reverse=True)
        return declared
    for parent in metadata.tables:
        for child in metadata.tables:
            if parent.name == child.name:
                continue
            for parent_col, child_col in _shared_relationship_columns(parent, child):
                phrase_score = _relationship_phrase_score(parent, child, parent_terms, child_terms, resolved_child)
                if phrase_score > 0:
                    inferred.append((phrase_score + 2.0, parent, child, parent_col, child_col))
    inferred.sort(key=lambda item: (item[0], item[2].score, item[1].score, item[2].name), reverse=True)
    return inferred


def _relationship_phrase_score(
    parent: TableMetadata,
    child: TableMetadata,
    parent_terms: list[str],
    child_terms: list[str],
    resolved_child: TableMetadata | None,
) -> float:
    score = 0.0
    child_match = False
    if resolved_child and child.name == resolved_child.name:
        score += 8.0
        child_match = True
    if child_terms and terms_match_table(child_terms, child):
        score += 6.0
        child_match = True
    if parent_terms and terms_match_table(parent_terms, parent):
        score += 6.0
    if not parent_terms and not child_terms:
        return 0.0
    if child_terms and any(_term_matches_columns(term, child) for term in child_terms):
        score += 2.0
        child_match = True
    if parent_terms and any(_term_matches_columns(term, parent) for term in parent_terms):
        score += 2.0
    return score if child_match else 0.0


def _term_matches_columns(term: str, table: TableMetadata) -> bool:
    variants = {term.lower(), term.lower().rstrip("s")}
    return any(any(variant and variant in column.lower() for variant in variants) for column in table.columns)


def _shared_relationship_columns(parent: TableMetadata, child: TableMetadata) -> list[tuple[str, str]]:
    parent_columns = {column.lower(): column for column in parent.columns}
    child_columns = {column.lower(): column for column in child.columns}
    shared: list[tuple[str, str]] = []
    parent_primary = {column.lower() for column in parent.primary_key or []}
    for lowered, parent_col in parent_columns.items():
        child_col = child_columns.get(lowered)
        if child_col and _looks_like_relationship_key(parent_col) and lowered in parent_primary:
            shared.append((parent_col, child_col))
    parent_name_tokens = _identifier_parts(parent.name)
    for child_lower, child_col in child_columns.items():
        if not _looks_like_relationship_key(child_lower):
            continue
        child_tokens = _identifier_parts(child_col)
        if parent_name_tokens and parent_name_tokens <= child_tokens:
            parent_id = next(iter(parent.primary_key or []), None) or _find_column(parent, ("id",))
            if parent_id:
                shared.append((parent_id, child_col))
    return list(dict.fromkeys(shared))


def _looks_like_relationship_key(column: str) -> bool:
    lowered = column.lower()
    if lowered.replace("_", "") in {"correlationid", "businesskey", "externalid", "referenceid"}:
        return False
    parts = _identifier_parts(column)
    return (
        lowered == "id"
        or lowered.endswith(("_id", "_key", "_ref"))
        or lowered.endswith("id")
    )


def _identity_column(table: TableMetadata, avoid: set[str] | None = None) -> str | None:
    avoid_l = {column.lower() for column in avoid or set()}
    for column in table.primary_key or []:
        if column in table.columns and column.lower() not in avoid_l:
            return column
    table_parts = _identifier_parts(table.name)
    named_ids = [
        column
        for column in table.columns
        if column.lower().endswith("_id")
        and column.lower() not in avoid_l
        and _identifier_parts(column) & table_parts
    ]
    if named_ids:
        return sorted(named_ids, key=lambda column: (len(column), column))[0]
    generic = _find_column(table, ("id",))
    if generic and generic.lower() not in avoid_l:
        return generic
    return None


def _infer_duplicate_child_flow(metadata: MetadataSearchResult, entities: EntityExtractionResult) -> DuplicateChildFlow | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for infer duplicate child flow within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for missing child candidate query within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    status_select = f"p.{flow.parent_status} AS parent_status," if flow.parent_status else "NULL AS parent_status,"
    child_label_select = f"c.{flow.child_label} AS child_reference," if flow.child_label else "NULL AS child_reference,"
    key_filter = ""
    if flow.parent_key_value:
        escaped = flow.parent_key_value.replace("'", "''")
        key_filter = f" AND p.{flow.parent_label} = '{escaped}'"
    child_match = _expected_child_join_filter(flow)
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
LEFT JOIN {flow.child_table.name} c ON c.{flow.child_fk_to_parent} = p.{flow.parent_id}{child_match}
WHERE c.{flow.child_id} IS NULL{key_filter}
ORDER BY p.{flow.parent_label}
""".strip()


def _missing_child_summary_query(flow: MissingChildFlow) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for missing child summary query within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    key_filter = ""
    if flow.parent_key_value:
        escaped = flow.parent_key_value.replace("'", "''")
        key_filter = f" AND p.{flow.parent_label} = '{escaped}'"
    child_match = _expected_child_join_filter(flow)
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
    LEFT JOIN {flow.child_table.name} c
        ON c.{flow.child_fk_to_parent} = p.{flow.parent_id}{child_match}
    WHERE c.{flow.child_id} IS NULL{key_filter}
) missing_related_candidates
GROUP BY issue_type
ORDER BY issue_count DESC
""".strip()


def _upstream_transition_query(flow: MissingChildFlow) -> str:
    columns = list(dict.fromkeys([flow.parent_id, flow.parent_label, flow.parent_status]))
    selected = ", ".join(column for column in columns if column)
    where = ""
    if flow.parent_key_value:
        escaped = flow.parent_key_value.replace("'", "''")
        where = f" WHERE {flow.parent_label} = '{escaped}'"
    return f"SELECT {selected} FROM {flow.parent_table.name}{where}"


def _expected_child_join_filter(flow: MissingChildFlow) -> str:
    descriptor_columns = [
        column
        for column in flow.child_table.columns
        if any(
            marker in column.lower()
            for marker in ("business", "name", "type", "detail", "description", "reference")
        )
    ]
    if not descriptor_columns or not flow.expected_child_terms:
        return ""
    term_filters: list[str] = []
    for term in flow.expected_child_terms:
        escaped = term.replace("'", "''")
        term_filters.append(
            "(" + " OR ".join(
                f"LOWER({_cast_to_text(f'c.{column}', flow.engine_type)}) LIKE '%{escaped}%'"
                for column in descriptor_columns
            ) + ")"
        )
    return " AND " + " AND ".join(term_filters)


def _downstream_records_for_parent_query(flow: MissingChildFlow) -> str:
    child_columns = list(
        dict.fromkeys(
            [
                flow.child_id,
                flow.child_fk_to_parent,
                flow.child_label,
                *(
                    column
                    for column in flow.child_table.columns
                    if any(
                        marker in column.lower()
                        for marker in ("business", "status", "correlation", "reference")
                    )
                ),
            ]
        )
    )
    selected = ", ".join(f"c.{column}" for column in child_columns if column)
    where = ""
    if flow.parent_key_value:
        escaped = flow.parent_key_value.replace("'", "''")
        where = f" WHERE p.{flow.parent_label} = '{escaped}'"
    return (
        f"SELECT {selected} FROM {flow.parent_table.name} p "
        f"JOIN {flow.child_table.name} c ON c.{flow.child_fk_to_parent} = p.{flow.parent_id}{where}"
    )


def _missing_flow_diagnostic_queries(
    metadata: MetadataSearchResult,
    entities: EntityExtractionResult,
    flow: MissingChildFlow,
) -> list[PlannedQuery]:
    """Inspect generic workflow diagnostics without assuming a domain schema."""
    problem = parse_problem_phrase(" ".join(entities.business_keywords or []))
    terms = [
        term.lower()
        for term in dict.fromkeys([*problem.target_terms, "missing", "absent", "failed"])
        if len(term) >= 4
    ][:6]
    queries: list[PlannedQuery] = []
    for table in metadata.tables:
        if table.name in {flow.parent_table.name, flow.child_table.name}:
            continue
        if not is_diagnostic_object(table.name):
            continue
        searchable = [
            column
            for column in table.columns
            if any(
                marker in column.lower()
                for marker in (
                    "detail",
                    "message",
                    "description",
                    "error",
                    "reason",
                    "status",
                    "key",
                    "correlation",
                    "reference",
                )
            )
        ]
        filters: list[str] = []
        if flow.parent_key_value:
            escaped = flow.parent_key_value.replace("'", "''")
            for column in searchable:
                if any(marker in column.lower() for marker in ("key", "correlation", "reference")):
                    filters.append(f"{_cast_to_text(column, metadata.engine_type)} = '{escaped}'")
        text_columns = [
            column
            for column in searchable
            if any(
                marker in column.lower()
                for marker in ("detail", "message", "description", "error", "reason")
            )
        ]
        for column in text_columns:
            for term in terms:
                escaped_term = term.replace("'", "''")
                filters.append(
                    f"LOWER({_cast_to_text(column, metadata.engine_type)}) "
                    f"LIKE '%{escaped_term}%'"
                )
        if not filters:
            continue
        columns = ", ".join(table.columns[:8]) if table.columns else "*"
        queries.append(
            PlannedQuery(
                purpose=(
                    "Inspect workflow exception, integration, audit, or batch evidence in "
                    f"{table.name}"
                ),
                sql=(
                    f"SELECT {columns} FROM {table.name} WHERE "
                    f"{' OR '.join(dict.fromkeys(filters))}"
                ),
            )
        )
    return queries[:4]


def _duplicate_child_query(flow: DuplicateChildFlow) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate child query within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    return _duplicate_child_query_for_engine(flow, None)


def _duplicate_parent_lookup_query(flow: DuplicateChildFlow) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate parent lookup query within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    escaped = (flow.parent_key_value or "").replace("'", "''")
    child_count_alias = f"{flow.child_table.name.split('.')[-1].rstrip('s')}_count"
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate child detail query for engine within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate child query for engine within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    child_name = flow.child_table.name.split(".")[-1].rstrip("s")
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate like investigation within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    if intent == InvestigationIntent.DUPLICATE_DATA:
        return True
    if intent != InvestigationIntent.PRODUCTION_INVESTIGATION:
        return False
    text = " ".join([entities.suspected_issue or "", *(entities.business_keywords or [])]).lower()
    return any(term in text for term in ("duplicate", "duplicated", "two", "multiple", "double", "created twice"))


def plan_safe_queries(
    intent: InvestigationIntent,
    metadata: MetadataSearchResult,
    entities: EntityExtractionResult,
    debug_events: list[dict[str, Any]] | None = None,
) -> list[PlannedQuery]:
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
    transfer_primary = _transfer_primary_query(metadata, entities)
    if transfer_primary:
        planned.append(transfer_primary)
    max_queries = 12 if transfer_primary else 8
    missing_child_flow = _infer_missing_child_flow(metadata, entities) if intent == InvestigationIntent.MISSING_DATA else None
    duplicate_child_flow = _infer_duplicate_child_flow(metadata, entities) if _duplicate_like_investigation(intent, entities) else None
    if intent in {InvestigationIntent.PROCESS_FLOW_BREAK, InvestigationIntent.PRODUCTION_INVESTIGATION}:
        planned.extend(_status_investigation_queries(metadata, entities))
    if intent in {InvestigationIntent.HEALTH_ASSESSMENT, InvestigationIntent.GENERAL_DATABASE_QUESTION}:
        planned.extend(_analytical_summary_queries(metadata, entities))
    if missing_child_flow:
        planned.extend(
            [
                PlannedQuery(
                    purpose="Verify upstream entity and current transition status",
                    sql=_upstream_transition_query(missing_child_flow),
                ),
                PlannedQuery(
                    purpose="Check downstream records under expected or alternate identifiers",
                    sql=_downstream_records_for_parent_query(missing_child_flow),
                ),
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
        planned.extend(_missing_flow_diagnostic_queries(metadata, entities, missing_child_flow))
    planned.extend(_entity_and_condition_queries(metadata, entities))
    planned.extend(_supporting_transfer_relationship_queries(metadata, entities, debug_events=debug_events))
    if duplicate_child_flow:
        planned.extend(
            [
                PlannedQuery(
                    purpose=(
                        "Resolve parent business key in "
                        f"{duplicate_child_flow.parent_table.name}"
                    ),
                    sql=_duplicate_parent_lookup_query(duplicate_child_flow),
                ),
                PlannedQuery(
                    purpose=(
                        f"Find duplicate {duplicate_child_flow.child_table.name} per "
                        f"{duplicate_child_flow.parent_table.name}"
                    ),
                    sql=_duplicate_child_query_for_engine(
                        duplicate_child_flow,
                        metadata.engine_type,
                    ),
                ),
                PlannedQuery(
                    purpose=(
                        f"Inspect {duplicate_child_flow.child_table.name} rows through "
                        f"{duplicate_child_flow.parent_table.name} key"
                    ),
                    sql=_duplicate_child_detail_query_for_engine(
                        duplicate_child_flow,
                        metadata.engine_type,
                    ),
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
    for table in metadata.tables[:3]:
        if table.name.lower() in targeted_duplicate_tables:
            continue
        where_clause = _where_for_table(table, entities, metadata.engine_type)
        columns = ", ".join(table.columns[:8]) if table.columns else "*"
        planned.append(PlannedQuery(purpose=f"Inspect relevant rows in {table.name}", sql=f"SELECT {columns} FROM {table.name}{where_clause}"))
    if _duplicate_like_investigation(intent, entities):
        key_values = _business_key_values(entities)
        duplicate_tables = sorted(metadata.tables[:5], key=lambda table: (table.score, _header_rank(table), len(table.name)), reverse=True)
        for table in duplicate_tables:
            if table.name.lower() in targeted_duplicate_tables:
                continue
            unique_cols = [
                column
                for index in table.indexes or []
                if index.get("unique")
                for column in index.get("columns", [])
                if column in table.columns
            ]
            natural_key_cols = _natural_key_columns(table)
            candidate_cols = list(dict.fromkeys([*unique_cols, *natural_key_cols]))
            if candidate_cols:
                col = candidate_cols[0]
                where = ""
                if key_values:
                    value_filters = []
                    for value in key_values:
                        escaped = value.replace("'", "''")
                        value_filters.append(f"{_cast_to_text(col, metadata.engine_type)} = '{escaped}'")
                    where = f" WHERE {' OR '.join(value_filters)}"
                planned.append(
                    PlannedQuery(
                        purpose=f"Find duplicate business keys in {table.name}",
                        sql=f"SELECT {col}, COUNT(*) AS duplicate_count FROM {table.name}{where} GROUP BY {col} HAVING COUNT(*) > 1",
                    )
                )
                planned.append(
                    PlannedQuery(
                        purpose=f"Inspect duplicate rows in {table.name}",
                        sql=f"SELECT {', '.join(table.columns[:8])} FROM {table.name}{where}",
                    )
                )
    staged: list[PlannedQuery] = []
    for index, query in enumerate(planned, start=1):
        staged_query = PlannedQuery(
            purpose=query.purpose,
            sql=query.sql,
            risk=query.risk,
            query_id=f"Q-{index}",
        )
        _record_plan_event(debug_events, query=staged_query, status="planned", reason="candidate_created")
        logger.info("evidence_plan planned %s %s", staged_query.query_id, staged_query.purpose)
        sql = ensure_limit(staged_query.sql)
        if sql != staged_query.sql:
            _record_plan_event(debug_events, query=staged_query, status="planned", reason="normalized_sql")
            staged_query = PlannedQuery(
                purpose=staged_query.purpose,
                sql=sql,
                risk=staged_query.risk,
                query_id=staged_query.query_id,
            )
        staged.append(staged_query)

    validated: list[PlannedQuery] = []
    seen_sql: set[str] = set()
    for query in staged:
        dedup_key = re.sub(r"\s+", " ", query.sql.strip()).lower()
        if dedup_key in seen_sql:
            _record_plan_event(
                debug_events,
                query=query,
                status="rejected",
                reason="deduplication:duplicate_sql_after_normalization",
            )
            logger.info("evidence_plan rejected %s duplicate_sql_after_normalization", query.query_id)
            continue
        seen_sql.add(dedup_key)
        try:
            validate_read_only_sql(query.sql)
        except ValueError as exc:
            _record_plan_event(
                debug_events,
                query=query,
                status="rejected",
                reason=f"validator_rejected:{exc}",
            )
            logger.warning("evidence_plan rejected %s %s", query.query_id, exc)
            continue
        _record_plan_event(debug_events, query=query, status="validated", reason="read_only_validator_passed")
        validated.append(query)

    safe = validated[:max_queries]
    for dropped in validated[max_queries:]:
        _record_plan_event(
            debug_events,
            query=dropped,
            status="rejected",
            reason="relationship_filtering:max_query_limit",
        )
        logger.info("evidence_plan rejected %s max_query_limit", dropped.query_id)
    return safe


def _cast_to_text(expression: str, engine_type: str | None) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for cast to text within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for string aggregate within safe_sql_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in safe_sql_service.py.
    
    Where it fits in the flow:
        Intent and metadata -> safe SQL planner -> validator -> evidence collector.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
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
