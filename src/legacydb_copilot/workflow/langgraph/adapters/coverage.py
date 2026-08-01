from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from legacydb_copilot.workflow.langgraph.enums import (
    CoverageStatus,
    WorkflowReasoningMode,
)
from legacydb_copilot.workflow.langgraph.state import InvestigationState


@dataclass(frozen=True)
class CoverageAdapter:
    def __call__(self, state: InvestigationState):
        required = list(dict.fromkeys(item.qualified_name for item in state["required_objects"]))
        successful = set(state["successful_objects"])
        inaccessible = set(state["inaccessible_objects"])
        missing = [name for name in required if name not in successful]
        blocking = any(gap.blocking for gap in [*state["metadata_gaps"], *state["evidence_gaps"]])
        percentage = 100.0 * (len(required) - len(missing)) / len(required) if required else 0.0
        limit = (
            state["planning_round"] >= state["max_planning_rounds"]
            or state["query_count"] >= state["max_queries"]
            or state["object_count"] >= state["max_objects"]
            or state["no_progress_rounds"] >= state["no_progress_limit"]
            or (state["deadline_at"] is not None and datetime.now(UTC) >= state["deadline_at"])
        )
        if not required:
            status = CoverageStatus.NOT_STARTED
        elif not missing and not blocking:
            status = CoverageStatus.COMPLETE
        elif limit:
            status = CoverageStatus.LIMIT_REACHED
        elif inaccessible & set(missing):
            status = CoverageStatus.BLOCKED
        else:
            status = CoverageStatus.PARTIAL
        return {
            "coverage_status": status,
            "coverage_percentage": percentage,
            "missing_required_objects": missing,
            "replan_reason": (
                ""
                if status == CoverageStatus.COMPLETE
                else "Required evidence remains missing within safe limits."
            ),
        }


@dataclass(frozen=True)
class DeterministicAssessmentAdapter:
    def __call__(self, state: InvestigationState):
        verified = bool(state["verified_evidence_ids"])
        blocked = state["coverage_status"] in {CoverageStatus.BLOCKED, CoverageStatus.LIMIT_REACHED}
        if not verified:
            mode = WorkflowReasoningMode.NO_VERIFIED_EVIDENCE
            reason = "No durable verified evidence is available."
        elif blocked or state["coverage_status"] != CoverageStatus.COMPLETE:
            mode = WorkflowReasoningMode.INSUFFICIENT_EVIDENCE
            reason = "Verified evidence exists, but required coverage is incomplete."
        else:
            mode = WorkflowReasoningMode.NORMAL_ROOT_CAUSE
            reason = "Verified evidence and complete required coverage are available."
        return {
            "reasoning_allowed": verified and not blocked,
            "reasoning_mode": mode,
            "provider_call_required": False,
            "reasoning_decision_reason": reason,
            "llm_skip_reason": "LG-06 does not invoke an LLM.",
        }


def coverage_route(state: InvestigationState) -> str:
    if state["cancel_requested"]:
        return "finalize"
    if state["coverage_status"] == CoverageStatus.PARTIAL:
        return "create_plan"
    return "assess_evidence"
