from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legacydb_copilot.workflow.langgraph.enums import CandidateStatus, EvidenceOutcome
from legacydb_copilot.workflow.langgraph.state import (
    CandidateObjectRecord,
    InvestigationState,
)


def candidates_from_discovery(state: InvestigationState) -> list[CandidateObjectRecord]:
    """Preserve several discovered objects; lexical score is intentionally only one signal."""
    existing = {item.candidate_id: item for item in state["ranked_candidates"]}
    candidates = list(state["ranked_candidates"])
    for rank, item in enumerate(state["candidate_objects"], start=1):
        candidate_id = f"{item.object_type}:{item.qualified_name}".casefold()
        if candidate_id in existing:
            continue
        lexical = max(0.0, 1.0 - ((rank - 1) * 0.1))
        structural = 1.0 / (1.0 + item.dependency_distance)
        candidates.append(
            CandidateObjectRecord(
                candidate_id=candidate_id,
                object_type=item.object_type,
                object_name=item.object_name,
                schema_name=item.schema_name,
                rank=rank,
                score=lexical + structural,
                lexical_relevance=lexical,
                structural_relevance=structural,
                path_role=item.path_role,
                reasons=(item.relevance_reason or "Discovered from live metadata.",),
            )
        )
    return candidates[: state["max_candidate_tables"] + state["max_candidate_code_objects"]]


@dataclass(frozen=True)
class CandidateSelectionAdapter:
    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        candidates = candidates_from_discovery(state)
        selectable = [
            item
            for item in candidates
            if item.status in {CandidateStatus.UNVERIFIED, CandidateStatus.INSUFFICIENT}
            and item.attempt_count == 0
        ]
        selectable.sort(
            key=lambda item: (
                item.entity_probe_result == "MATCHED",
                item.structural_relevance,
                item.semantic_relevance,
                item.knowledge_relevance,
                item.lexical_relevance,
                -item.rank,
            ),
            reverse=True,
        )
        if not selectable:
            return {
                "ranked_candidates": candidates,
                "active_candidate_id": "",
                "stop_reason": "Candidate exploration exhausted within configured limits.",
            }
        selected = selectable[0]
        updated = [
            item.model_copy(update={"attempt_count": item.attempt_count + 1})
            if item.candidate_id == selected.candidate_id
            else item
            for item in candidates
        ]
        trace = [
            *state["candidate_transition_trace"],
            {
                "node": "select_candidate",
                "candidate_id": selected.candidate_id,
                "decision": "selected",
                "reason": "Highest bounded evidence-priority candidate not previously attempted.",
                "backtrack_count": state["backtrack_count"],
                "expansion_count": state["expansion_count"],
            },
        ]
        return {
            "ranked_candidates": updated,
            "active_candidate_id": selected.candidate_id,
            "candidate_transition_trace": trace,
            "graph_step_count": state["graph_step_count"] + 1,
        }


@dataclass(frozen=True)
class CandidateEvaluationAdapter:
    """Classify the active candidate from persisted, structured read-only findings."""

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        active = next(
            (
                item
                for item in state["ranked_candidates"]
                if item.candidate_id == state["active_candidate_id"]
            ),
            None,
        )
        if active is None:
            return {"stop_reason": "No active candidate is available for evaluation."}
        object_name = active.qualified_name.casefold()
        findings = [
            item
            for item in state["findings"]
            if item.object_name.casefold() == object_name
            or item.object_name.casefold().split(".")[-1] == active.object_name.casefold()
        ]
        supporting_outcomes = {
            EvidenceOutcome.VALUE_PRESENT,
            EvidenceOutcome.POSITIVE_ROWS,
            EvidenceOutcome.NULL_VALUE,
            EvidenceOutcome.REQUIRED_VALUE_MISSING,
            EvidenceOutcome.UNEXPECTED_NULL,
            EvidenceOutcome.CALCULATION_NOT_POSSIBLE,
        }
        matching = [item for item in findings if item.finding_type in supporting_outcomes]
        contradicted = [
            item
            for item in findings
            if item.finding_type is EvidenceOutcome.NO_MATCHING_ROW
        ]
        evidence_ids = tuple(
            result.evidence_id
            for result in state["query_results"]
            if result.evidence_id
            and any(name.casefold() == object_name for name in result.referenced_objects)
        )
        if matching:
            status = CandidateStatus.SUPPORTED
            reason = "A bounded read-only probe returned matching database evidence."
            entity_result = "MATCHED"
            supporting = evidence_ids
            opposing: tuple[str, ...] = ()
        elif contradicted:
            status = CandidateStatus.CONTRADICTED
            reason = "A bounded read-only probe returned no matching row; candidate contradicted."
            entity_result = "NOT_FOUND"
            supporting = ()
            opposing = evidence_ids
        else:
            status = CandidateStatus.INSUFFICIENT
            reason = "Probe evidence neither supported nor contradicted this candidate."
            entity_result = "INCONCLUSIVE"
            supporting = ()
            opposing = ()
        updated = [
            item.model_copy(
                update={
                    "status": status,
                    "entity_probe_result": entity_result,
                    "supporting_evidence_ids": supporting,
                    "contradicting_evidence_ids": opposing,
                    "decision_reason": reason,
                    "score": item.score + (
                        100.0
                        if status is CandidateStatus.SUPPORTED
                        else -100.0
                        if status is CandidateStatus.CONTRADICTED
                        else 0.0
                    ),
                }
            )
            if item.candidate_id == active.candidate_id
            else item
            for item in state["ranked_candidates"]
        ]
        trace = [
            *state["candidate_transition_trace"],
            {
                "node": "evaluate_candidate",
                "candidate_id": active.candidate_id,
                "decision": status.value,
                "reason": reason,
                "backtrack_count": state["backtrack_count"],
                "expansion_count": state["expansion_count"],
            },
        ]
        return {
            "ranked_candidates": updated,
            "candidate_transition_trace": trace,
            "graph_step_count": state["graph_step_count"] + 1,
        }


def candidate_route(state: InvestigationState) -> str:
    if state["cancel_requested"] or state["graph_step_count"] >= state["max_graph_steps"]:
        return "assess_evidence"
    active = next(
        (
            item
            for item in state["ranked_candidates"]
            if item.candidate_id == state["active_candidate_id"]
        ),
        None,
    )
    if active is None or active.status is CandidateStatus.SUPPORTED:
        return "check_coverage"
    if active.status is CandidateStatus.CONTRADICTED:
        return "reject_candidate"
    if active.status is CandidateStatus.REJECTED:
        if state["backtrack_count"] >= state["max_backtracks"]:
            return "assess_evidence"
        remaining = any(
            item.status is CandidateStatus.UNVERIFIED
            for item in state["ranked_candidates"]
        )
        return "select_candidate" if remaining else "expand_discovery"
    if active.status is CandidateStatus.INSUFFICIENT:
        return "expand_discovery"
    return "check_coverage"


@dataclass(frozen=True)
class CandidateRejectionAdapter:
    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        active_id = state["active_candidate_id"]
        updated = [
            item.model_copy(
                update={
                    "status": CandidateStatus.REJECTED,
                    "decision_reason": (
                        item.decision_reason
                        or "Contradicting read-only evidence rejected this candidate."
                    ),
                }
            )
            if item.candidate_id == active_id
            and item.status is CandidateStatus.CONTRADICTED
            else item
            for item in state["ranked_candidates"]
        ]
        backtracks = state["backtrack_count"] + 1
        return {
            "ranked_candidates": updated,
            "backtrack_count": backtracks,
            "active_candidate_id": "",
            "candidate_transition_trace": [
                *state["candidate_transition_trace"],
                {
                    "node": "reject_candidate",
                    "candidate_id": active_id,
                    "decision": CandidateStatus.REJECTED.value,
                    "reason": "Contradicting evidence caused bounded backtracking.",
                    "backtrack_count": backtracks,
                    "expansion_count": state["expansion_count"],
                },
            ],
            "graph_step_count": state["graph_step_count"] + 1,
        }


def rejection_route(state: InvestigationState) -> str:
    if state["backtrack_count"] >= state["max_backtracks"]:
        return "assess_evidence"
    remaining = any(
        item.status is CandidateStatus.UNVERIFIED for item in state["ranked_candidates"]
    )
    if remaining:
        return "select_candidate"
    if state["expansion_count"] < state["max_expansions"]:
        return "expand_discovery"
    return "assess_evidence"


@dataclass(frozen=True)
class CandidateExpansionAdapter:
    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        if state["expansion_count"] >= state["max_expansions"]:
            return {"stop_reason": "Candidate expansion budget exhausted."}
        expansion = state["expansion_count"] + 1
        return {
            "expansion_count": expansion,
            "active_candidate_id": "",
            "replan_reason": "Current candidate was unsupported; expand bounded discovery.",
            "candidate_transition_trace": [
                *state["candidate_transition_trace"],
                {
                    "node": "expand_discovery",
                    "decision": "expanded",
                    "reason": "No supported candidate remained in the current discovery window.",
                    "backtrack_count": state["backtrack_count"],
                    "expansion_count": expansion,
                },
            ],
            "graph_step_count": state["graph_step_count"] + 1,
        }
