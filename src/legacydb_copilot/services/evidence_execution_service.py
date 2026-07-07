from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from legacydb_copilot.config import Settings
from legacydb_copilot.services.safe_sql_service import PlannedQuery, ProductionReadSafetyValidator, validate_read_only_sql


@dataclass(frozen=True)
class EvidenceResult:
    purpose: str
    sql: str
    rows: list[dict[str, Any]]
    error: str | None = None
    original_sql: str | None = None
    safety_note: str | None = None


def execute_evidence_plan(connector, plan: list[PlannedQuery]) -> list[EvidenceResult]:
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
    validator = ProductionReadSafetyValidator(
        max_rows=settings.max_investigation_rows,
        allow_full_table_scan=settings.allow_full_table_scan,
        row_estimates=_row_estimates_for_plan(connector, plan),
        engine_type=str(getattr(connector, "engine_type", "") or getattr(connector, "engine", "") or ""),
    )
    for query in plan:
        try:
            validate_read_only_sql(query.sql)
            safe_read = validator.validate(query.sql)
            rows = connector.execute_read_only_query(safe_read.sql, limit=settings.max_investigation_rows)
            evidence.append(
                EvidenceResult(
                    query.purpose,
                    safe_read.sql,
                    rows,
                    original_sql=query.sql if safe_read.changed else None,
                    safety_note=safe_read.reason or None,
                )
            )
        except Exception as exc:
            evidence.append(EvidenceResult(query.purpose, query.sql, [], str(exc)))
    return evidence


def _row_estimates_for_plan(connector, plan: list[PlannedQuery]) -> dict[str, int]:
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
                estimates[table_name.lower().split(".")[-1]] = value
    return estimates
