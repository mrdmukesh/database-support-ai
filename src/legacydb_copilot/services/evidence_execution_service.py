from __future__ import annotations

import inspect
import logging
import re
from dataclasses import dataclass, field
from itertools import count
from typing import Any, Literal

from legacydb_copilot.config import Settings
from legacydb_copilot.services.safe_sql_service import (
    PlannedQuery,
    ProductionReadSafetyValidator,
    ScanPolicyViolation,
    validate_read_only_sql,
)
from legacydb_copilot.services.scan_policy_service import ScanPolicy
from legacydb_copilot.services.sql_dialect_service import resolve_sql_dialect, validate_sql_dialect

_evidence_id_sequence = count(1)
logger = logging.getLogger(__name__)


def _next_evidence_id() -> str:
    return f"SQL-{next(_evidence_id_sequence)}"


@dataclass(frozen=True)
class EvidenceResult:
    purpose: str
    sql: str
    rows: list[dict[str, Any]]
    error: str | None = None
    original_sql: str | None = None
    safety_note: str | None = None
    evidence_id: str = field(default_factory=_next_evidence_id)
    execution_status: Literal[
        "succeeded",
        "failed",
        "blocked",
        "permission_denied",
        "timed_out",
    ] = "succeeded"
    evidence_semantics: Literal[
        "positive_rows",
        "verified_absence",
        "aggregate",
        "metadata",
        "null_value",
        "procedure_definition",
        "procedure_execution",
        "not_applicable",
        "execution_failure",
    ] = "not_applicable"
    supports_claim: str = ""
    evidence_relevance: Literal["relevant", "irrelevant", "unverified"] = "unverified"
    scan_policy_decision: dict[str, Any] = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def zero_row_result(self) -> bool:
        return self.execution_status == "succeeded" and self.row_count == 0


def execute_evidence_plan(
    connector,
    plan: list[PlannedQuery],
    plan_statuses: list[dict[str, Any]] | None = None,
    *,
    provider: Any | None = None,
    scan_policy: ScanPolicy | None = None,
    workspace_id: str = "",
    connection_id: str = "",
) -> list[EvidenceResult]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Executes the planned investigation SQL and converts returned rows/errors into structured evidence.

    Input:
        Database connector and safe SQL plan generated from intent, entities, and metadata.

    Output:
        EvidenceResult list containing purpose, executed SQL, returned rows, and any safety adjustments/errors.

    Called by:
        Main /chat/ask orchestration after Safe SQL Planner creates read-only candidate queries.

    Flow:
        Safe SQL Planner -> SafeSQLValidator -> ProductionReadSafetyValidator -> connector.execute_read_only_query.

    Safety:
        Every query is validated as read-only, optionally limited for production safety, and executed with row limits.
    """

    evidence: list[EvidenceResult] = []
    settings = Settings.from_env()
    trusted_provider = (
        provider
        if provider is not None
        else (
            getattr(connector, "database_engine", None)
            or getattr(connector, "engine_type", None)
        )
    )
    dialect = resolve_sql_dialect(trusted_provider)
    validator = ProductionReadSafetyValidator(
        max_rows=settings.max_investigation_rows,
        allow_full_table_scan=settings.allow_full_table_scan,
        row_estimates=_row_estimates_for_plan(connector, plan),
        engine_type=dialect.value,
        scan_policy=scan_policy,
    )
    for index, query in enumerate(plan, start=1):
        policy_decision: dict[str, Any] = {}
        try:
            execution_sql = query.execution_sql or query.sql
            validate_sql_dialect(
                execution_sql,
                dialect,
                planner_step="evidence_execution_preflight",
                query_id=query.query_id or f"Q-{index}",
            )
            validate_read_only_sql(execution_sql)
            safe_read = validator.validate(execution_sql)
            policy_decision = (
                safe_read.policy_decision.to_dict()
                if safe_read.policy_decision is not None
                else {}
            )
            validate_sql_dialect(
                safe_read.sql,
                dialect,
                planner_step="production_read_safety",
                query_id=query.query_id or f"Q-{index}",
            )
            logger.info(
                "scan_policy_decision workspace_id=%s connection_id=%s "
                "environment=%s policy=%s decision=%s reason=%s component=%s",
                workspace_id,
                connection_id,
                policy_decision.get("environment_type", "UNRESOLVED"),
                policy_decision.get("policy", "UNRESOLVED_STRICT_READ_ONLY"),
                policy_decision.get("decision", "allowed"),
                policy_decision.get("reason", "read_only_validation_passed"),
                "ProductionReadSafetyValidator",
            )
            rows = _execute_read_only_query(
                connector,
                safe_read.sql,
                settings.max_investigation_rows,
                query.parameters,
            )
            semantics, supports_claim = _successful_evidence_semantics(query, safe_read.sql, rows)
            if plan_statuses is not None:
                plan_statuses.append(
                    {
                        "query_id": query.query_id or f"Q-{index}",
                        "purpose": query.purpose,
                        "status": "executed",
                        "reason": safe_read.reason or "executed_successfully",
                        "row_count": len(rows),
                        "sql": safe_read.sql,
                        "scan_policy_decision": policy_decision,
                    }
                )
            logger.info("evidence_plan executed %s rows=%s", query.query_id or f"Q-{index}", len(rows))
            evidence.append(
                EvidenceResult(
                    query.purpose,
                    safe_read.sql,
                    rows,
                    original_sql=query.sql if safe_read.changed else None,
                    safety_note=safe_read.reason or None,
                    evidence_id=f"SQL-{index}",
                    execution_status="succeeded",
                    evidence_semantics=semantics,
                    supports_claim=supports_claim,
                    evidence_relevance="relevant",
                    scan_policy_decision=policy_decision,
                )
            )
        except Exception as exc:
            execution_status = _failed_execution_status(exc)
            if isinstance(exc, ScanPolicyViolation):
                policy_decision = exc.decision.to_dict()
            if plan_statuses is not None:
                plan_statuses.append(
                    {
                        "query_id": query.query_id or f"Q-{index}",
                        "purpose": query.purpose,
                        "status": "failed",
                        "reason": str(exc),
                        "row_count": 0,
                        "sql": query.sql,
                        "scan_policy_decision": policy_decision,
                    }
                )
            logger.warning("evidence_plan failed %s %s", query.query_id or f"Q-{index}", exc)
            evidence.append(
                EvidenceResult(
                    query.purpose,
                    query.sql,
                    [],
                    str(exc),
                    evidence_id=f"SQL-{index}",
                    execution_status=execution_status,
                    evidence_semantics="execution_failure",
                    scan_policy_decision=policy_decision,
                )
            )
    return evidence


def _execute_read_only_query(
    connector,
    sql: str,
    limit: int,
    parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    execute = connector.execute_read_only_query
    if "parameters" in inspect.signature(execute).parameters:
        return execute(
            sql,
            limit=limit,
            parameters=parameters,
        )
    return execute(sql, limit=limit)


def _successful_evidence_semantics(
    query: PlannedQuery,
    sql: str,
    rows: list[dict[str, Any]],
) -> tuple[str, str]:
    normalized = f"{query.purpose} {sql}".casefold()
    declared = getattr(query, "evidence_semantics", "not_applicable")
    if re.search(r"\b(count\s*\(|exists\s*\(|not\s+exists\b)", sql, re.I):
        values = [value for row in rows for value in row.values()]
        zero = bool(values) and all(
            isinstance(value, (int, float, bool)) and int(value) == 0 for value in values
        )
        return "aggregate", (
            f"The aggregate/existence query completed and verified a zero outcome for: {query.purpose}."
            if zero
            else f"The aggregate/existence query completed for: {query.purpose}."
        )
    if rows:
        null_columns = sorted(
            {
                str(column)
                for row in rows
                for column, value in row.items()
                if value is None
            }
        )
        if declared == "null_value" or null_columns:
            detail = (
                f" (NULL columns: {', '.join(null_columns)})"
                if null_columns
                else ""
            )
            return (
                "null_value",
                f"Returned rows verify NULL source data{detail} for: {query.purpose}.",
            )
        return "positive_rows", f"{len(rows)} verified row(s) support: {query.purpose}."
    absence_markers = (
        "missing", "without", "orphan", "not exist", "no matching", "downstream",
        "related record", "duplicate", "absence",
    )
    if declared == "verified_absence" or any(marker in normalized for marker in absence_markers):
        return "verified_absence", (
            f"The query executed successfully and found no matching rows for: {query.purpose}."
        )
    return "not_applicable", ""


def _failed_execution_status(
    exc: Exception,
) -> Literal["failed", "blocked", "permission_denied", "timed_out"]:
    text = f"{type(exc).__name__} {exc}".casefold()
    if "timeout" in text or "timed out" in text:
        return "timed_out"
    if isinstance(exc, PermissionError) or any(
        marker in text
        for marker in (
            "access denied",
            "insufficient privilege",
            "permission denied",
            "permission was denied",
            "not authorized",
        )
    ):
        return "permission_denied"
    if any(
        marker in text for marker in (
            "blocked", "rejected", "safety", "policy",
            "only select", "read-only", "read only",
        )
    ):
        return "blocked"
    return "failed"


def _row_estimates_for_plan(connector, plan: list[PlannedQuery]) -> dict[str, int]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for row estimates for plan within evidence_execution_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_execution_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    estimate = getattr(connector, "estimate_table_rows", None)
    if not callable(estimate):
        return {}
    estimates: dict[str, int] = {}
    for query in plan:
        for match in re.finditer(r"\bfrom\s+([`\"\[\]\w.]+)", query.sql, re.I):
            table_name = str(match.group(1)).strip("`[]\"")
            if "." in table_name and table_name.lower().startswith("information_schema."):
                continue
            try:
                value = estimate(table_name)
            except Exception:
                continue
            if isinstance(value, int):
                estimates[table_name.lower()] = value
    return estimates
