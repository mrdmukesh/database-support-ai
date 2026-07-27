from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult


class GapQuestionType(StrEnum):
    AFFECTED_ENTITY = "AFFECTED_ENTITY"
    EXPECTED_STATE = "EXPECTED_STATE"
    ACTUAL_STATE = "ACTUAL_STATE"
    RELATIONSHIPS = "RELATIONSHIPS"
    WORKFLOW = "WORKFLOW"
    RUNTIME_EXECUTION = "RUNTIME_EXECUTION"
    LAST_SUCCESSFUL_STEP = "LAST_SUCCESSFUL_STEP"
    FIRST_FAILED_STEP = "FIRST_FAILED_STEP"
    PROCEDURE_OWNERSHIP = "PROCEDURE_OWNERSHIP"
    EXCEPTIONS = "EXCEPTIONS"
    REPRODUCTION = "REPRODUCTION"
    EXTERNAL_EVIDENCE = "EXTERNAL_EVIDENCE"


class GapPriority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class GapStatus(StrEnum):
    OPEN = "OPEN"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    QUERY_FAILED = "QUERY_FAILED"
    CONTRADICTED = "CONTRADICTED"
    BLOCKED_BY_MISSING_SOURCE = "BLOCKED_BY_MISSING_SOURCE"


class EvidenceSourceType(StrEnum):
    DATABASE = "DATABASE"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class RecommendedEvidence:
    source_type: EvidenceSourceType
    evidence_type: str
    description: str


@dataclass(frozen=True)
class EvidenceGap:
    gap_id: str
    question_type: GapQuestionType
    question: str
    priority: GapPriority
    required_for_goal: bool
    status: GapStatus
    source_type: EvidenceSourceType
    supporting_evidence_refs: tuple[str, ...]
    recommended_next_evidence: RecommendedEvidence
    reason: str


@dataclass(frozen=True)
class EvidenceContradiction:
    description: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceGapAnalysis:
    status: str
    gaps: tuple[EvidenceGap, ...]
    answered_questions: tuple[GapQuestionType, ...]
    evidence_summary: dict[str, int] = field(default_factory=dict)


_QUESTIONS = {
    GapQuestionType.AFFECTED_ENTITY: "Which exact business entity is affected?",
    GapQuestionType.EXPECTED_STATE: "What verified state was expected?",
    GapQuestionType.ACTUAL_STATE: "What state is verified in runtime evidence?",
    GapQuestionType.RELATIONSHIPS: "Which verified relationships connect the affected records?",
    GapQuestionType.WORKFLOW: "What verified workflow path applies?",
    GapQuestionType.RUNTIME_EXECUTION: "Did the relevant operation execute at runtime?",
    GapQuestionType.LAST_SUCCESSFUL_STEP: "What was the last successful workflow step?",
    GapQuestionType.FIRST_FAILED_STEP: "What was the first failed workflow step?",
    GapQuestionType.PROCEDURE_OWNERSHIP: "Which procedure owns the relevant write path?",
    GapQuestionType.EXCEPTIONS: "Were relevant exceptions recorded or verified absent?",
    GapQuestionType.REPRODUCTION: "Was the reported condition reproduced?",
    GapQuestionType.EXTERNAL_EVIDENCE: "What external evidence confirms the runtime path?",
}


def detect_evidence_gaps(
    *,
    evidence: Iterable[EvidenceResult],
    evidence_gate: EvidenceGateResult | None,
    procedure_analysis: Iterable[Any] = (),
    expected_state_rule: str = "",
    affected_entity_verified: bool | None = None,
    external_evidence_required: bool = False,
    external_evidence_refs: Iterable[str] = (),
    contradictions: Iterable[EvidenceContradiction] = (),
) -> EvidenceGapAnalysis:
    """Classify unanswered investigation questions from supplied evidence only."""
    items = tuple(evidence)
    procedures = tuple(procedure_analysis)
    contradiction_items = tuple(contradictions)
    external_refs = tuple(dict.fromkeys(external_evidence_refs))
    successful = tuple(
        item for item in items if item.execution_status == "succeeded" and not item.error
    )
    failed = tuple(
        item
        for item in items
        if item.execution_status in {"failed", "timed_out"}
        or (bool(item.error) and item.execution_status not in {"blocked"})
    )
    blocked = tuple(item for item in items if item.execution_status == "blocked")
    verified_absence = tuple(
        item
        for item in successful
        if item.evidence_semantics == "verified_absence" and item.zero_row_result
    )
    metadata_only = tuple(
        item
        for item in successful
        if item.evidence_semantics in {"metadata", "procedure_definition"}
    )
    runtime = tuple(
        item
        for item in successful
        if item.evidence_semantics not in {"metadata", "procedure_definition"}
        and (bool(item.rows) or item in verified_absence)
    )
    answered: set[GapQuestionType] = set()
    entity_is_verified = (
        affected_entity_verified
        if affected_entity_verified is not None
        else bool(evidence_gate and evidence_gate.business_key_exists)
    )
    if entity_is_verified:
        answered.add(GapQuestionType.AFFECTED_ENTITY)
    if expected_state_rule.strip() or (evidence_gate and evidence_gate.expected_value):
        answered.add(GapQuestionType.EXPECTED_STATE)
    if runtime:
        answered.add(GapQuestionType.ACTUAL_STATE)
    if evidence_gate and evidence_gate.parent_child_relationship_exists:
        answered.add(GapQuestionType.RELATIONSHIPS)
    if _has_runtime_marker(runtime, ("workflow", "history", "step", "job", "instance")):
        answered.add(GapQuestionType.WORKFLOW)
    if _has_runtime_marker(runtime, ("runtime", "execution", "workflow", "history", "step", "job")):
        answered.add(GapQuestionType.RUNTIME_EXECUTION)
    if _has_row_state(runtime, ("success", "succeeded", "complete", "completed")):
        answered.add(GapQuestionType.LAST_SUCCESSFUL_STEP)
    if _has_row_state(runtime, ("fail", "failed", "error", "exception")):
        answered.add(GapQuestionType.FIRST_FAILED_STEP)
    if any(
        getattr(item, "definition_available", False) and bool(getattr(item, "tables_written", ()))
        for item in procedures
    ):
        answered.add(GapQuestionType.PROCEDURE_OWNERSHIP)
    if _has_runtime_marker(runtime, ("exception", "error", "failure")):
        answered.add(GapQuestionType.EXCEPTIONS)
    if evidence_gate and evidence_gate.reproduced:
        answered.add(GapQuestionType.REPRODUCTION)
    if not external_evidence_required or external_refs:
        answered.add(GapQuestionType.EXTERNAL_EVIDENCE)

    gaps: list[EvidenceGap] = []
    if contradiction_items:
        gaps.append(
            _gap(
                GapQuestionType.ACTUAL_STATE,
                GapPriority.CRITICAL,
                GapStatus.CONTRADICTED,
                EvidenceSourceType.DATABASE,
                tuple(
                    dict.fromkeys(ref for item in contradiction_items for ref in item.evidence_refs)
                ),
                "Resolve contradictory verified evidence before selecting an actual state.",
                "Contradictory evidence leaves the actual state unresolved.",
                "contradiction_resolution",
            )
        )
        answered.discard(GapQuestionType.ACTUAL_STATE)

    for item in failed:
        gaps.append(
            _gap(
                GapQuestionType.RUNTIME_EXECUTION,
                GapPriority.HIGH,
                GapStatus.QUERY_FAILED,
                EvidenceSourceType.DATABASE,
                (item.evidence_id,),
                "Correct or safely retry the failed bounded read through the validated SQL path.",
                "A failed SQL query is not verified absence.",
                "bounded_runtime_query",
            )
        )
        answered.discard(GapQuestionType.RUNTIME_EXECUTION)
    for item in blocked:
        gaps.append(
            _gap(
                GapQuestionType.RUNTIME_EXECUTION,
                GapPriority.HIGH,
                GapStatus.POLICY_BLOCKED,
                EvidenceSourceType.DATABASE,
                (item.evidence_id,),
                "Resolve the policy limitation or provide a narrower validated read.",
                "A policy-blocked SQL query is not verified absence.",
                "policy_compliant_runtime_query",
            )
        )
        answered.discard(GapQuestionType.RUNTIME_EXECUTION)

    required_questions = set(GapQuestionType)
    if not external_evidence_required:
        required_questions.remove(GapQuestionType.EXTERNAL_EVIDENCE)
    existing = {(item.question_type, item.status) for item in gaps}
    for question_type in GapQuestionType:
        if question_type in answered or any(key[0] is question_type for key in existing):
            continue
        source = (
            EvidenceSourceType.EXTERNAL
            if question_type is GapQuestionType.EXTERNAL_EVIDENCE
            else EvidenceSourceType.DATABASE
        )
        status = (
            GapStatus.BLOCKED_BY_MISSING_SOURCE
            if source is EvidenceSourceType.EXTERNAL
            else GapStatus.OPEN
        )
        gaps.append(
            _gap(
                question_type,
                _priority(question_type),
                status,
                source,
                _relevant_refs(question_type, successful, metadata_only),
                _recommendation(question_type, source),
                _reason(question_type, metadata_only),
                _evidence_type(question_type),
                required_for_goal=question_type in required_questions,
            )
        )
    gaps.sort(key=lambda item: (_priority_rank(item.priority), item.question_type.value))
    return EvidenceGapAnalysis(
        status="COMPLETE" if not gaps else "GAPS_IDENTIFIED",
        gaps=tuple(gaps),
        answered_questions=tuple(sorted(answered, key=lambda item: item.value)),
        evidence_summary={
            "verified_runtime": len(runtime),
            "verified_absence": len(verified_absence),
            "metadata_only": len(metadata_only),
            "failed_queries": len(failed),
            "blocked_queries": len(blocked),
            "contradictions": len(contradiction_items),
            "external_evidence": len(external_refs),
        },
    )


def _gap(
    question_type: GapQuestionType,
    priority: GapPriority,
    status: GapStatus,
    source_type: EvidenceSourceType,
    refs: tuple[str, ...],
    recommendation: str,
    reason: str,
    evidence_type: str,
    *,
    required_for_goal: bool = True,
) -> EvidenceGap:
    return EvidenceGap(
        gap_id=f"GAP-{question_type.value}",
        question_type=question_type,
        question=_QUESTIONS[question_type],
        priority=priority,
        required_for_goal=required_for_goal,
        status=status,
        source_type=source_type,
        supporting_evidence_refs=refs,
        recommended_next_evidence=RecommendedEvidence(
            source_type,
            evidence_type,
            recommendation,
        ),
        reason=reason,
    )


def _has_runtime_marker(
    evidence: Iterable[EvidenceResult],
    markers: tuple[str, ...],
) -> bool:
    return any(
        any(marker in f"{item.purpose} {item.supports_claim}".casefold() for marker in markers)
        for item in evidence
    )


def _has_row_state(
    evidence: Iterable[EvidenceResult],
    states: tuple[str, ...],
) -> bool:
    return any(
        any(
            any(state in str(value).casefold() for state in states)
            for key, value in row.items()
            if any(marker in key.casefold() for marker in ("status", "state", "step", "result"))
        )
        for item in evidence
        for row in item.rows
    )


def _relevant_refs(
    question_type: GapQuestionType,
    successful: tuple[EvidenceResult, ...],
    metadata_only: tuple[EvidenceResult, ...],
) -> tuple[str, ...]:
    source = metadata_only if question_type is GapQuestionType.PROCEDURE_OWNERSHIP else successful
    return tuple(item.evidence_id for item in source[:5])


def _priority(question_type: GapQuestionType) -> GapPriority:
    if question_type in {
        GapQuestionType.AFFECTED_ENTITY,
        GapQuestionType.EXPECTED_STATE,
        GapQuestionType.ACTUAL_STATE,
        GapQuestionType.REPRODUCTION,
    }:
        return GapPriority.CRITICAL
    if question_type in {
        GapQuestionType.RUNTIME_EXECUTION,
        GapQuestionType.FIRST_FAILED_STEP,
        GapQuestionType.RELATIONSHIPS,
    }:
        return GapPriority.HIGH
    return GapPriority.MEDIUM


def _priority_rank(priority: GapPriority) -> int:
    return {
        GapPriority.CRITICAL: 0,
        GapPriority.HIGH: 1,
        GapPriority.MEDIUM: 2,
        GapPriority.LOW: 3,
    }[priority]


def _recommendation(
    question_type: GapQuestionType,
    source: EvidenceSourceType,
) -> str:
    if source is EvidenceSourceType.EXTERNAL:
        return "Obtain the scoped application log, message-queue trace, or external runtime record."
    recommendations = {
        GapQuestionType.AFFECTED_ENTITY: "Perform an exact, bounded business-key lookup.",
        GapQuestionType.EXPECTED_STATE: (
            "Provide a verified expected-state rule or approved specification."
        ),
        GapQuestionType.ACTUAL_STATE: (
            "Collect a bounded runtime-state query for the affected entity."
        ),
        GapQuestionType.RELATIONSHIPS: "Verify foreign keys or bounded relationship joins.",
        GapQuestionType.WORKFLOW: "Collect bounded workflow or status-history evidence.",
        GapQuestionType.RUNTIME_EXECUTION: "Collect runtime execution-history evidence.",
        GapQuestionType.LAST_SUCCESSFUL_STEP: (
            "Collect ordered workflow steps identifying the last success."
        ),
        GapQuestionType.FIRST_FAILED_STEP: (
            "Collect ordered workflow steps identifying the first failure."
        ),
        GapQuestionType.PROCEDURE_OWNERSHIP: (
            "Inspect procedure dependencies and verified write targets."
        ),
        GapQuestionType.EXCEPTIONS: "Collect bounded exception evidence or verified absence.",
        GapQuestionType.REPRODUCTION: (
            "Collect evidence required by the deterministic reproduction rule."
        ),
        GapQuestionType.EXTERNAL_EVIDENCE: "",
    }
    return recommendations[question_type]


def _reason(
    question_type: GapQuestionType,
    metadata_only: tuple[EvidenceResult, ...],
) -> str:
    if question_type is GapQuestionType.RUNTIME_EXECUTION and metadata_only:
        return "Procedure or object metadata does not prove runtime execution."
    return "No verified evidence answers this investigation question."


def _evidence_type(question_type: GapQuestionType) -> str:
    return {
        GapQuestionType.AFFECTED_ENTITY: "ENTITY_LOOKUP",
        GapQuestionType.EXPECTED_STATE: "EXPECTED_STATE_RULE",
        GapQuestionType.ACTUAL_STATE: "RUNTIME_STATE",
        GapQuestionType.RELATIONSHIPS: "FOREIGN_KEY_TRACE",
        GapQuestionType.WORKFLOW: "WORKFLOW_TRACE",
        GapQuestionType.RUNTIME_EXECUTION: "RUNTIME_EXECUTION_HISTORY",
        GapQuestionType.LAST_SUCCESSFUL_STEP: "ORDERED_WORKFLOW_HISTORY",
        GapQuestionType.FIRST_FAILED_STEP: "ORDERED_WORKFLOW_HISTORY",
        GapQuestionType.PROCEDURE_OWNERSHIP: "PROCEDURE_DEPENDENCY",
        GapQuestionType.EXCEPTIONS: "EXCEPTION_LOOKUP",
        GapQuestionType.REPRODUCTION: "REPRODUCTION_EVIDENCE",
        GapQuestionType.EXTERNAL_EVIDENCE: "EXTERNAL_RUNTIME_EVIDENCE",
    }[question_type]
