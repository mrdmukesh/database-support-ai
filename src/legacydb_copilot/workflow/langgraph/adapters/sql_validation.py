from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from legacydb_copilot.services.safe_sql_service import validate_read_only_sql
from legacydb_copilot.workflow.langgraph.enums import QueryValidationStatus
from legacydb_copilot.workflow.langgraph.state import InvestigationState, QueryRecord


@dataclass(frozen=True)
class SQLValidationAdapter:
    authorize_scope: Callable[[InvestigationState, QueryRecord], None]
    production_safety: Callable[[str], str]

    def __call__(self, state: InvestigationState):
        approved: list[QueryRecord] = []
        rejected = list(state["rejected_queries"])
        hashes = list(state["rejected_query_hashes"])
        for query in state["proposed_queries"]:
            try:
                self.authorize_scope(state, query)
                validate_read_only_sql(query.sanitized_sql)
                bounded_sql = self.production_safety(query.sanitized_sql)
                approved.append(
                    query.model_copy(
                        update={
                            "sanitized_sql": bounded_sql,
                            "validation_status": QueryValidationStatus.APPROVED,
                            "read_only": True,
                            "validated_at": datetime.now(UTC),
                        }
                    )
                )
            except Exception as exc:
                rejected.append(
                    query.model_copy(
                        update={
                            "validation_status": QueryValidationStatus.REJECTED,
                            "rejection_code": type(exc).__name__,
                            "rejection_reason": str(exc),
                            "validated_at": datetime.now(UTC),
                        }
                    )
                )
                if query.query_hash not in hashes:
                    hashes.append(query.query_hash)
        return {
            "approved_queries": approved,
            "rejected_queries": rejected,
            "rejected_query_hashes": hashes,
        }
