from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.enums import EvidenceOutcome, QueryExecutionStatus
from legacydb_copilot.workflow.langgraph.state import (
    EvidenceGapRecord,
    FindingRecord,
    InvestigationState,
    QueryRecord,
)

PersistEvidence = Callable[[InvestigationState, QueryRecord, tuple[FindingRecord, ...]], str]


@dataclass(frozen=True)
class EvidencePreservationAdapter:
    persist: PersistEvidence

    def __call__(self, state: InvestigationState):
        ids = list(state["evidence_ids"])
        verified = list(state["verified_evidence_ids"])
        gaps = list(state["evidence_gaps"])
        findings = list(state["findings"])
        updated_results: list[QueryRecord] = []
        successful = list(state["successful_objects"])
        failed = list(state["failed_objects"])
        inaccessible = list(state["inaccessible_objects"])
        completed = list(state["completed_plan_steps"])
        for result in state["query_results"]:
            if result.evidence_id:
                updated_results.append(result)
                continue
            query_findings, gap = _classify(result, state)
            if gap:
                gaps.append(gap)
                if result.execution_status == QueryExecutionStatus.PERMISSION_DENIED:
                    inaccessible.extend(result.referenced_objects)
                else:
                    failed.extend(result.referenced_objects)
                updated_results.append(result)
                continue
            try:
                evidence_id = self.persist(state, result, tuple(query_findings))
            except Exception as exc:
                raise OperationalNodeError(
                    "EVIDENCE_PERSISTENCE_FAILED",
                    "Executed result could not be durably persisted.",
                    context={"query_id": result.query_id, "detail": str(exc)},
                ) from exc
            durable = result.model_copy(
                update={
                    "evidence_id": evidence_id,
                    "result_reference": evidence_id,
                }
            )
            updated_results.append(durable)
            findings.extend(query_findings)
            if evidence_id not in ids:
                ids.append(evidence_id)
            if evidence_id not in verified:
                verified.append(evidence_id)
            successful.extend(result.referenced_objects)
            if result.plan_step_id not in completed:
                completed.append(result.plan_step_id)
        return {
            "query_results": updated_results,
            "evidence_ids": ids,
            "verified_evidence_ids": verified,
            "evidence_gaps": gaps,
            "findings": findings,
            "successful_objects": list(dict.fromkeys(successful)),
            "failed_objects": list(dict.fromkeys(failed)),
            "inaccessible_objects": list(dict.fromkeys(inaccessible)),
            "completed_plan_steps": completed,
        }


def _classify(
    result: QueryRecord,
    state: InvestigationState,
) -> tuple[list[FindingRecord], EvidenceGapRecord | None]:
    if result.execution_status == QueryExecutionStatus.TIMED_OUT:
        return [], _gap("query_timed_out", "The bounded query timed out.", result)
    if result.execution_status == QueryExecutionStatus.PERMISSION_DENIED:
        return [], _gap("permission_blocked", "Query permission was denied.", result)
    if result.execution_status in {
        QueryExecutionStatus.FAILED,
        QueryExecutionStatus.BLOCKED,
        QueryExecutionStatus.CANCELLED,
    }:
        return [], _gap("query_failed", "The query did not produce durable evidence.", result)
    if result.execution_status == QueryExecutionStatus.SUCCEEDED_EMPTY:
        return [_finding(EvidenceOutcome.NO_MATCHING_ROW, result, "No matching row.")], None
    if result.execution_status == QueryExecutionStatus.SUCCEEDED_WITH_NULLS:
        null_columns = {
            str(column)
            for row in result.result_summary
            for column, value in row.items()
            if value is None
        }
        required = _required_columns(result, state)
        values: list[FindingRecord] = []
        for column in sorted(null_columns):
            outcome = (
                EvidenceOutcome.REQUIRED_VALUE_MISSING
                if column.casefold() in required
                else EvidenceOutcome.OPTIONAL_VALUE_NULL
            )
            values.append(_finding(outcome, result, f"{column} is NULL.", column=column))
            step = next(
                (
                    item
                    for item in state["investigation_plan"]
                    if item.step_id == result.plan_step_id
                ),
                None,
            )
            if (
                outcome == EvidenceOutcome.REQUIRED_VALUE_MISSING
                and step is not None
                and "CALCULATION" in step.query_intent.upper()
            ):
                values.append(
                    _finding(
                        EvidenceOutcome.CALCULATION_NOT_POSSIBLE,
                        result,
                        "A required calculation input is NULL.",
                        column=column,
                    )
                )
        if len(result.referenced_objects) > 1 and null_columns:
            values.append(
                _finding(
                    EvidenceOutcome.RELATIONSHIP_NOT_PRESENT,
                    result,
                    "The joined relationship target was absent.",
                )
            )
        return values, None
    return [_finding(EvidenceOutcome.VALUE_PRESENT, result, "Bounded values were returned.")], None


def _required_columns(result: QueryRecord, state: InvestigationState) -> set[str]:
    step = next(
        (item for item in state["investigation_plan"] if item.step_id == result.plan_step_id),
        None,
    )
    text = step.evidence_sought if step else ""
    return {part.casefold() for part in text.replace(",", " ").split()}


def _finding(
    outcome: EvidenceOutcome,
    result: QueryRecord,
    description: str,
    *,
    column: str = "",
) -> FindingRecord:
    return FindingRecord(
        finding_type=outcome,
        object_name=result.referenced_objects[0] if result.referenced_objects else "",
        column_name=column,
        description=description,
        blocking=outcome
        in {
            EvidenceOutcome.REQUIRED_VALUE_MISSING,
            EvidenceOutcome.CALCULATION_NOT_POSSIBLE,
        },
    )


def _gap(kind: str, description: str, result: QueryRecord) -> EvidenceGapRecord:
    return EvidenceGapRecord(
        gap_type=kind,
        description=description,
        affected_object=result.referenced_objects[0] if result.referenced_objects else "",
        blocking=True,
        source_node="preserve_evidence",
        timestamp=datetime.now(UTC),
    )
