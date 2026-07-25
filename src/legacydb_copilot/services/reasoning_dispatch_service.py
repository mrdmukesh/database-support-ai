from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult


class ReasoningPermission(StrEnum):
    ALLOW_REASONING = "ALLOW_REASONING"
    DENY_REASONING = "DENY_REASONING"


class ReasoningMode(StrEnum):
    NORMAL_ROOT_CAUSE = "NORMAL_ROOT_CAUSE"
    EVIDENCE_SUMMARY_NOT_REPRODUCED = "EVIDENCE_SUMMARY_NOT_REPRODUCED"
    SKIP = "SKIP"


@dataclass(frozen=True)
class ReasoningDispatchDecision:
    permission: ReasoningPermission
    mode: ReasoningMode
    reason: str


def dispatch_reasoning(gate: EvidenceGateResult) -> ReasoningDispatchDecision:
    """Select how to reason only after the evidence gate has decided permission."""
    permission = ReasoningPermission(gate.reasoning_permission)
    if permission == ReasoningPermission.DENY_REASONING:
        return ReasoningDispatchDecision(
            permission=permission,
            mode=ReasoningMode.SKIP,
            reason=gate.permission_reason or "Verified deterministic evidence is unavailable.",
        )
    if gate.reproduced:
        return ReasoningDispatchDecision(
            permission=permission,
            mode=ReasoningMode.NORMAL_ROOT_CAUSE,
            reason="Verified evidence reproduced the reported condition.",
        )
    return ReasoningDispatchDecision(
        permission=permission,
        mode=ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
        reason="Verified evidence exists, but the reported condition was not reproduced.",
    )
