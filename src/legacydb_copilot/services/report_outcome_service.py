from __future__ import annotations

from dataclasses import dataclass

from legacydb_copilot.agents.reasoning_agent import ReasoningResult, RootCauseSupportStatus


@dataclass(frozen=True)
class ReportOutcome:
    """Authoritative presentation view of the final investigation state."""

    root_cause_verified: bool
    summary: str
    root_cause_items: tuple[str, ...]
    why_it_happened_items: tuple[str, ...]
    recommendation_items: tuple[str, ...]
    supporting_evidence_items: tuple[str, ...]


def compose_report_outcome(reasoning: ReasoningResult) -> ReportOutcome:
    """Give final deterministic VERIFIED evidence authority over generated prose."""
    verified_claims = tuple(
        claim
        for claim in getattr(reasoning, "likely_root_causes", ())
        if getattr(claim, "status", None) is RootCauseSupportStatus.VERIFIED
    )
    is_verified = getattr(reasoning, "response_type", "") == "confirmed_root_cause" or bool(verified_claims)

    if is_verified:
        root_items = tuple(str(claim) for claim in verified_claims) or (
            str(getattr(reasoning, "summary", "Confirmed root cause.")),
        )
        why_items = tuple(
            dict.fromkeys(
                [
                    *(claim.conclusion for claim in verified_claims),
                    *getattr(reasoning, "confirmed_facts", ()),
                ]
            )
        ) or root_items
        recommendations = tuple(
            str(item) for item in getattr(reasoning, "recommended_fix", ()) if str(item).strip()
        ) or (
            "Review the verified causal condition and validate a controlled corrective change before implementation.",
        )
    else:
        root_items = ("Root cause not established from the available evidence.",)
        why_items = ("No causal event chain was established from the available evidence.",)
        recommendations = (
            "No corrective action is recommended because root cause is not established.",
            "Collect the missing evidence identified above before proposing a fix.",
        )

    return ReportOutcome(
        root_cause_verified=is_verified,
        summary=(root_items[0] if is_verified else str(getattr(reasoning, "summary", ""))),
        root_cause_items=root_items,
        why_it_happened_items=why_items,
        recommendation_items=recommendations,
        supporting_evidence_items=tuple(getattr(reasoning, "supporting_evidence", ())),
    )
