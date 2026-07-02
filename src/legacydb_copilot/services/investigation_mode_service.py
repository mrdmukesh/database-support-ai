from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from legacydb_copilot.agents.intent_agent import InvestigationIntent, IntentResult


class InvestigationMode(StrEnum):
    INVESTIGATION = "INVESTIGATION"
    KNOWLEDGE_SEARCH = "KNOWLEDGE_SEARCH"
    BUSINESS_RULE_DISCOVERY = "BUSINESS_RULE_DISCOVERY"


@dataclass(frozen=True)
class ModeClassification:
    mode: InvestigationMode
    confidence: float
    rationale: str
    required_stages: list[str]


_KNOWLEDGE_SEARCH_MARKERS = (
    "approved knowledge",
    "approved issue",
    "known issue",
    "knowledge base",
    "knowledge article",
    "previous investigation",
    "previous issue",
    "past issue",
    "similar issue",
    "similarity",
    "reusable fix",
    "runbook",
    "document",
    "docs",
    "uploaded",
    "have we seen",
    "search knowledge",
    "search documents",
)

_BUSINESS_RULE_MARKERS = (
    "business rule",
    "business rules",
    "rule discovery",
    "discover rule",
    "allowed status",
    "allowed statuses",
    "status values",
    "validation rule",
    "process document",
    "procedure logic",
    "stored procedure logic",
    "constraints",
    "schema rule",
    "how does",
    "how is",
    "what are the rules",
    "what is the rule",
    "explain the rule",
    "explain process",
)

_LIVE_INVESTIGATION_INTENTS = {
    InvestigationIntent.PRODUCTION_INVESTIGATION,
    InvestigationIntent.PERFORMANCE_INVESTIGATION,
    InvestigationIntent.PROCESS_FLOW_BREAK,
    InvestigationIntent.DUPLICATE_DATA,
    InvestigationIntent.MISSING_DATA,
    InvestigationIntent.FAILED_BATCH_JOB,
    InvestigationIntent.RECONCILIATION_OR_MISMATCH,
    InvestigationIntent.IMPACT_ANALYSIS,
    InvestigationIntent.HEALTH_ASSESSMENT,
}


def classify_investigation_mode(question: str, intent: IntentResult | None = None) -> ModeClassification:
    lowered = question.lower()
    if any(marker in lowered for marker in _KNOWLEDGE_SEARCH_MARKERS):
        return ModeClassification(
            mode=InvestigationMode.KNOWLEDGE_SEARCH,
            confidence=0.86,
            rationale="Question asks for previous, approved, uploaded, or reusable knowledge rather than live database diagnosis.",
            required_stages=["question_understanding", "knowledge_retrieval", "semantic_ranking", "answer"],
        )
    if any(marker in lowered for marker in _BUSINESS_RULE_MARKERS) and not _looks_like_live_failure(intent, lowered):
        return ModeClassification(
            mode=InvestigationMode.BUSINESS_RULE_DISCOVERY,
            confidence=0.82,
            rationale="Question asks to discover rules, allowed values, constraints, or procedure logic without root-cause diagnosis.",
            required_stages=["question_understanding", "metadata_discovery", "knowledge_retrieval", "procedure_analysis", "answer"],
        )
    return ModeClassification(
        mode=InvestigationMode.INVESTIGATION,
        confidence=0.78,
        rationale="Question appears to require live evidence, metadata, safe SQL, evidence gate, and root-cause reasoning.",
        required_stages=[
            "question_understanding",
            "metadata_discovery",
            "safe_sql",
            "evidence_gate",
            "root_cause_analysis",
            "report_generation",
        ],
    )


def _looks_like_live_failure(intent: IntentResult | None, lowered: str) -> bool:
    if intent and intent.intent in _LIVE_INVESTIGATION_INTENTS:
        return any(
            marker in lowered
            for marker in (
                "why",
                "failed",
                "missing",
                "duplicate",
                "slow",
                "timeout",
                "broken",
                "not generated",
                "not created",
                "root cause",
            )
        )
    return False
