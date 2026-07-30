from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.workflow.langgraph.enums import QueryExecutionStatus, QueryValidationStatus
from legacydb_copilot.workflow.langgraph.state import InvestigationState


@dataclass(frozen=True)
class SQLExecutionAdapter:
    execute: Callable[[list[PlannedQuery]], list[EvidenceResult]]
    authorize: Callable[[InvestigationState], None]
    max_summary_rows: int = 5

    def __call__(self, state: InvestigationState):
        if state["cancel_requested"]:
            return {"terminal_status": "CANCELLED", "stop_reason": "Cancellation requested."}
        self.authorize(state)
        remaining = max(0, state["max_queries"] - state["query_count"])
        executed_ids = {query.query_id for query in state["query_results"]}
        executed_hashes = {query.query_hash for query in state["query_results"] if query.query_hash}
        approved = [
            query
            for query in state["approved_queries"]
            if query.validation_status == QueryValidationStatus.APPROVED
            and query.execution_status == QueryExecutionStatus.NOT_EXECUTED
            and query.query_id not in executed_ids
            and (not query.query_hash or query.query_hash not in executed_hashes)
        ][:remaining]
        planned = [
            PlannedQuery(query.query_id, query.sanitized_sql, query_id=query.query_id)
            for query in approved
        ]
        evidence = self.execute(planned) if planned else []
        results = list(state["query_results"])
        for query, item in zip(approved, evidence, strict=True):
            status = _status(item)
            results.append(
                query.model_copy(
                    update={
                        "execution_status": status,
                        "row_count": item.row_count,
                        "timed_out": status == QueryExecutionStatus.TIMED_OUT,
                        "error_classification": item.execution_status if item.error else "",
                        "execution_duration_ms": int(
                            item.scan_policy_decision.get("duration_ms", 0)
                        ),
                        "result_summary": tuple(item.rows[: self.max_summary_rows]),
                        "truncated": item.row_count > self.max_summary_rows,
                        "executed_at": datetime.now(UTC),
                    }
                )
            )
        return {"query_results": results, "query_count": state["query_count"] + len(approved)}


def _status(item: EvidenceResult) -> QueryExecutionStatus:
    if item.execution_status == "timed_out":
        return QueryExecutionStatus.TIMED_OUT
    if item.execution_status == "permission_denied":
        return QueryExecutionStatus.PERMISSION_DENIED
    if item.execution_status != "succeeded":
        return QueryExecutionStatus.FAILED
    if not item.rows:
        return QueryExecutionStatus.SUCCEEDED_EMPTY
    if any(value is None for row in item.rows for value in row.values()):
        return QueryExecutionStatus.SUCCEEDED_WITH_NULLS
    return QueryExecutionStatus.SUCCEEDED
