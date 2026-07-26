from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult


class ReasoningPermission(StrEnum):
    ALLOW_REASONING = "ALLOW_REASONING"
    DENY_REASONING = "DENY_REASONING"


class ReasoningMode(StrEnum):
    SKIP_NO_VERIFIED_EVIDENCE = "SKIP_NO_VERIFIED_EVIDENCE"
    NORMAL_ROOT_CAUSE = "NORMAL_ROOT_CAUSE"
    EVIDENCE_SUMMARY_NOT_REPRODUCED = "EVIDENCE_SUMMARY_NOT_REPRODUCED"
    EVIDENCE_GAP_SUMMARY = "EVIDENCE_GAP_SUMMARY"
    PARTIAL_EVIDENCE_SUMMARY = "PARTIAL_EVIDENCE_SUMMARY"
    SKIP = "SKIP_NO_VERIFIED_EVIDENCE"


class ReproductionStatus(StrEnum):
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    INDETERMINATE = "indeterminate"


class RootCauseSupport(StrEnum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class ReasoningDispatchDecision:
    permission: ReasoningPermission
    mode: ReasoningMode
    reason: str
    invoke_llm: bool
    verified_evidence_count: int
    reproduction_status: ReproductionStatus
    root_cause_support: RootCauseSupport
    reason_code: str
    evidence_categories: list[str]
    evidence_gaps: list[str]


def dispatch_reasoning(gate: EvidenceGateResult) -> ReasoningDispatchDecision:
    """Select reasoning from normalized evidence availability, independently of wording."""
    verified_count = gate.verified_evidence_count or int(gate.verified_evidence)
    permission = (
        ReasoningPermission.ALLOW_REASONING
        if verified_count > 0
        else ReasoningPermission.DENY_REASONING
    )
    condition_verified = gate.reproduced or gate.reported_condition_exists
    reproduction_status = (
        ReproductionStatus.REPRODUCED
        if condition_verified
        else ReproductionStatus.NOT_REPRODUCED
    )
    if permission == ReasoningPermission.DENY_REASONING:
        return ReasoningDispatchDecision(
            permission=permission,
            mode=ReasoningMode.SKIP_NO_VERIFIED_EVIDENCE,
            reason=gate.permission_reason or "Verified deterministic evidence is unavailable.",
            invoke_llm=False,
            verified_evidence_count=0,
            reproduction_status=reproduction_status,
            root_cause_support=RootCauseSupport.INSUFFICIENT,
            reason_code="NO_VERIFIED_EVIDENCE",
            evidence_categories=gate.evidence_categories,
            evidence_gaps=gate.evidence_gaps or gate.missing_evidence,
        )
    if condition_verified:
        return ReasoningDispatchDecision(
            permission=permission,
            mode=ReasoningMode.NORMAL_ROOT_CAUSE,
            reason="Verified evidence reproduced the reported condition.",
            invoke_llm=True,
            verified_evidence_count=verified_count,
            reproduction_status=reproduction_status,
            root_cause_support=RootCauseSupport.SUPPORTED,
            reason_code="VERIFIED_EVIDENCE_REPRODUCED",
            evidence_categories=gate.evidence_categories,
            evidence_gaps=gate.evidence_gaps or gate.missing_evidence,
        )
    mode = (
        ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED
        if reproduction_status == ReproductionStatus.NOT_REPRODUCED
        else ReasoningMode.EVIDENCE_GAP_SUMMARY
    )
    return ReasoningDispatchDecision(
        permission=permission,
        mode=mode,
        reason=(
            "Verified evidence was collected, but the reported condition could not be reproduced."
            if mode == ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED
            else "Verified evidence was collected, but reproduction and root cause remain indeterminate."
        ),
        invoke_llm=True,
        verified_evidence_count=verified_count,
        reproduction_status=reproduction_status,
        root_cause_support=RootCauseSupport.NOT_SUPPORTED,
        reason_code=(
            "VERIFIED_EVIDENCE_NOT_REPRODUCED"
            if mode == ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED
            else "VERIFIED_EVIDENCE_REPRODUCTION_INDETERMINATE"
        ),
        evidence_categories=gate.evidence_categories,
        evidence_gaps=gate.evidence_gaps or gate.missing_evidence,
    )
