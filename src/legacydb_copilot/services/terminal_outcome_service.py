from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from legacydb_copilot.db.models import InvestigationModel
from legacydb_copilot.services.investigation_state_machine import (
    TERMINAL_STATES,
    InvestigationState,
    InvestigationStateService,
    StateTransition,
)


def _normalized(value: object) -> str:
    return str(value or "").strip().casefold()


def resolve_canonical_terminal_outcome(
    *,
    reproduction_status: object = None,
    reasoning_mode: object = None,
    ai_outcome: object = None,
    workflow_status: object = None,
    policy_blocked: bool = False,
    insufficient_evidence: bool = False,
    reasoning_permission: object = None,
    verified_evidence_count: int | None = None,
    root_cause_requirements_satisfied: bool | None = None,
) -> InvestigationState | None:
    """Resolve semantic outcome only from explicit structured investigation signals."""
    reproduction = _normalized(reproduction_status)
    mode = _normalized(reasoning_mode)
    outcome = _normalized(ai_outcome)
    status = _normalized(workflow_status)
    permission = _normalized(reasoning_permission)

    if policy_blocked or status == "ai_skipped_by_policy" or outcome == "policy_blocked":
        return InvestigationState.POLICY_BLOCKED
    if (
        reproduction == "not_reproduced"
        or mode == "evidence_summary_not_reproduced"
        or outcome
        in {
            "evidence_summary_not_reproduced",
            "verified_evidence_not_reproduced",
        }
    ):
        return InvestigationState.ISSUE_NOT_REPRODUCED
    if (
        insufficient_evidence
        or status == "insufficient_database_evidence"
        or outcome == "insufficient_evidence"
        or mode
        in {
            "evidence_gap_summary",
            "skip_no_verified_evidence",
        }
        or verified_evidence_count == 0
    ):
        return InvestigationState.INSUFFICIENT_EVIDENCE
    if reproduction == "reproduced":
        if (
            permission == "allow_reasoning"
            and root_cause_requirements_satisfied is True
        ):
            return InvestigationState.ROOT_CAUSE_CONFIRMED
        if root_cause_requirements_satisfied is False:
            return InvestigationState.INSUFFICIENT_EVIDENCE
    return None


def resolve_legacy_terminal_outcome(
    workflow_status: object,
    trace: Mapping[str, Any] | None = None,
) -> InvestigationState | None:
    """Map only explicit, unambiguous legacy outcomes when no canonical state exists."""
    status = _normalized(workflow_status)
    if status == "ai_summarized_not_reproduced":
        return InvestigationState.ISSUE_NOT_REPRODUCED
    if status == "insufficient_database_evidence":
        return InvestigationState.INSUFFICIENT_EVIDENCE
    if status == "ai_skipped_by_policy":
        return InvestigationState.POLICY_BLOCKED

    trace = trace or {}
    mode = _normalized(trace.get("reasoning_mode"))
    outcome = _normalized(trace.get("ai_outcome"))
    if (
        mode == "evidence_summary_not_reproduced"
        or outcome == "evidence_summary_not_reproduced"
    ):
        return InvestigationState.ISSUE_NOT_REPRODUCED
    if mode in {"evidence_gap_summary", "skip_no_verified_evidence"} or outcome == (
        "insufficient_evidence"
    ):
        return InvestigationState.INSUFFICIENT_EVIDENCE
    if outcome == "policy_blocked":
        return InvestigationState.POLICY_BLOCKED
    return None


def persist_canonical_terminal_outcome(
    service: InvestigationStateService,
    investigation: InvestigationModel,
    outcome: InvestigationState,
    *,
    reason: str,
) -> StateTransition:
    """Persist one valid terminal path and leave an existing terminal untouched."""
    current = service.current(investigation.id)
    if current is None:
        current = service.initialize(investigation)
    if current.current_state in TERMINAL_STATES:
        return current
    if current.current_state is InvestigationState.INITIALIZATION:
        current = service.transition(
            investigation,
            InvestigationState.EVIDENCE_ASSESSMENT,
            reason="Assess the completed synchronous investigation outcome.",
        )

    if outcome is InvestigationState.POLICY_BLOCKED:
        if current.current_state is InvestigationState.EVIDENCE_ASSESSMENT:
            current = service.transition(
                investigation,
                InvestigationState.GAP_IDENTIFICATION,
                reason="Record the policy constraint identified during investigation.",
            )
        if current.current_state is InvestigationState.GAP_IDENTIFICATION:
            current = service.transition(
                investigation,
                InvestigationState.ACTION_SELECTION,
                reason="Select the governed policy outcome.",
            )
    return service.transition(investigation, outcome, reason=reason)
