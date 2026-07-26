from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from legacydb_copilot.services.evidence_execution_service import EvidenceResult


@dataclass(frozen=True)
class NormalizedEvidenceState:
    verified_evidence_count: int
    evidence_categories: list[str]
    evidence_gaps: list[str]

    @property
    def available(self) -> bool:
        return self.verified_evidence_count > 0


def normalize_verified_evidence(
    evidence: Iterable[EvidenceResult],
    *,
    procedure_analysis: Iterable[Any] = (),
    relevant_absence_ids: set[str] | None = None,
) -> NormalizedEvidenceState:
    """Classify verified evidence without using question wording or reproduction state."""
    categories: set[str] = set()
    gaps: set[str] = set()
    verified_count = 0

    for item in evidence:
        if item.execution_status != "succeeded" or item.error:
            gaps.add(
                "policy_blocked_query"
                if item.execution_status == "blocked"
                else "timed_out_query"
                if item.execution_status == "timed_out"
                else "failed_query"
            )
            continue

        category = _verified_category(
            item,
            relevant_absence_ids=relevant_absence_ids,
        )
        if category:
            verified_count += 1
            categories.add(category)

    for procedure in procedure_analysis:
        if getattr(procedure, "definition_available", False):
            verified_count += 1
            categories.add("procedure_definition")

    return NormalizedEvidenceState(
        verified_evidence_count=verified_count,
        evidence_categories=sorted(categories),
        evidence_gaps=sorted(gaps),
    )


def _verified_category(
    item: EvidenceResult,
    *,
    relevant_absence_ids: set[str] | None,
) -> str:
    semantics = item.evidence_semantics
    text = f"{item.purpose} {item.sql}".casefold()
    if (
        semantics == "verified_absence"
        and item.zero_row_result
        and (
            item.evidence_relevance == "relevant"
            or
            relevant_absence_ids is None
            or item.evidence_id in relevant_absence_ids
        )
    ):
        return "verified_absence"
    if semantics == "aggregate" and item.rows:
        return "aggregate"
    if semantics == "metadata":
        return "metadata"
    if semantics == "procedure_definition":
        return "procedure_definition"
    if (
        semantics == "positive_rows"
        and item.rows
        and item.supports_claim
        and item.evidence_relevance != "irrelevant"
    ):
        if any(marker in text for marker in ("workflow", "job", "history", "step", "instance")):
            return "workflow_rows"
        return "positive_sql_rows"
    if semantics == "not_applicable" and item.rows and item.sql.strip():
        return "positive_sql_rows"
    return ""
