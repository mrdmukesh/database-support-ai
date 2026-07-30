from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult
from legacydb_copilot.services.reasoning_dispatch_service import dispatch_reasoning
from legacydb_copilot.workflow.langgraph.enums import (
    CoverageStatus,
    WorkflowReasoningMode,
    WorkflowReproductionStatus,
)
from legacydb_copilot.workflow.langgraph.state import InvestigationState


@dataclass(frozen=True)
class EvidenceGateAdapter:
    run_gate: Callable[[InvestigationState, tuple[str, ...]], EvidenceGateResult]

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        if state["cancel_requested"]:
            return _skip(state, WorkflowReasoningMode.SKIP, "Investigation cancelled.")
        gate = self.run_gate(state, tuple(state["verified_evidence_ids"]))
        decision = dispatch_reasoning(gate)
        mode = {
            "NORMAL_ROOT_CAUSE": WorkflowReasoningMode.NORMAL_ROOT_CAUSE,
            "EVIDENCE_SUMMARY_NOT_REPRODUCED": (
                WorkflowReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED
            ),
            "EVIDENCE_GAP_SUMMARY": WorkflowReasoningMode.INSUFFICIENT_EVIDENCE,
            "PARTIAL_EVIDENCE_SUMMARY": WorkflowReasoningMode.INSUFFICIENT_EVIDENCE,
            "SKIP_NO_VERIFIED_EVIDENCE": WorkflowReasoningMode.NO_VERIFIED_EVIDENCE,
        }.get(decision.mode.value, WorkflowReasoningMode.SKIP)
        blockers = [
            gap.description
            for gap in [*state["metadata_gaps"], *state["evidence_gaps"]]
            if gap.blocking
        ]
        dynamic_blocker = any("dynamic" in value.casefold() for value in blockers)
        persistence_blocker = any(
            error.code in {"EVIDENCE_PERSISTENCE_FAILED", "REASONING_PERSISTENCE_FAILED"}
            for error in state["errors"]
        )
        allowed = decision.invoke_llm
        if state["coverage_status"] in {CoverageStatus.PARTIAL, CoverageStatus.LIMIT_REACHED}:
            mode = WorkflowReasoningMode.INSUFFICIENT_EVIDENCE
            allowed = False
        if (
            dynamic_blocker
            or persistence_blocker
            or state["coverage_status"] == CoverageStatus.BLOCKED
        ):
            mode = WorkflowReasoningMode.NEEDS_HUMAN_REVIEW
            allowed = False
        reproduction = (
            WorkflowReproductionStatus.REPRODUCED
            if gate.reproduced
            else WorkflowReproductionStatus.NOT_REPRODUCED
        )
        reason = (
            decision.reason
            if allowed
            else (
                "; ".join(blockers) or decision.reason or "Evidence Gate denied provider reasoning."
            )
        )
        gate_record = {
            **asdict(decision),
            "permission": decision.permission.value,
            "mode": decision.mode.value,
            "reproduction_status": decision.reproduction_status.value,
            "root_cause_support": decision.root_cause_support.value,
        }
        return {
            "evidence_gate_decision": gate_record,
            "reasoning_allowed": allowed,
            "reasoning_mode": mode,
            "provider_call_required": allowed,
            "llm_skip_reason": "" if allowed else reason,
            "reasoning_decision_reason": reason,
            "reasoning_blockers": blockers,
            "reasoning_warnings": list(gate.evidence_gaps),
            "reproduction_status": reproduction,
            "reproduction_checks_complete": True,
            "reproduction_explanation": gate.permission_reason,
        }


def _skip(state: InvestigationState, mode: WorkflowReasoningMode, reason: str) -> dict[str, Any]:
    return {
        "evidence_gate_decision": {"reason_code": "CANCELLED", "invoke_llm": False},
        "reasoning_allowed": False,
        "reasoning_mode": mode,
        "provider_call_required": False,
        "llm_skip_reason": reason,
        "reasoning_decision_reason": reason,
        "reasoning_blockers": [reason],
    }
