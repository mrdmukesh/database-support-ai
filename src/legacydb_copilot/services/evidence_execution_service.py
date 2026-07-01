from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legacydb_copilot.services.safe_sql_service import PlannedQuery, validate_read_only_sql


@dataclass(frozen=True)
class EvidenceResult:
    purpose: str
    sql: str
    rows: list[dict[str, Any]]
    error: str | None = None


def execute_evidence_plan(connector, plan: list[PlannedQuery]) -> list[EvidenceResult]:
    evidence: list[EvidenceResult] = []
    for query in plan:
        try:
            validate_read_only_sql(query.sql)
            rows = connector.execute_read_only_query(query.sql, limit=25)
            evidence.append(EvidenceResult(query.purpose, query.sql, rows))
        except Exception as exc:
            evidence.append(EvidenceResult(query.purpose, query.sql, [], str(exc)))
    return evidence
