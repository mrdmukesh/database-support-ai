from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InvestigationIntent(StrEnum):
    PRODUCTION_INVESTIGATION = "PRODUCTION_INVESTIGATION"
    PERFORMANCE_INVESTIGATION = "PERFORMANCE_INVESTIGATION"
    PROCESS_FLOW_BREAK = "PROCESS_FLOW_BREAK"
    DUPLICATE_DATA = "DUPLICATE_DATA"
    MISSING_DATA = "MISSING_DATA"
    FAILED_BATCH_JOB = "FAILED_BATCH_JOB"
    RECONCILIATION_OR_MISMATCH = "RECONCILIATION_OR_MISMATCH"
    STORED_PROCEDURE_ANALYSIS = "STORED_PROCEDURE_ANALYSIS"
    IMPACT_ANALYSIS = "IMPACT_ANALYSIS"
    TEST_CASE_GENERATION = "TEST_CASE_GENERATION"
    PROOF_OF_FIX = "PROOF_OF_FIX"
    HEALTH_ASSESSMENT = "HEALTH_ASSESSMENT"
    GENERAL_DATABASE_QUESTION = "GENERAL_DATABASE_QUESTION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IntentResult:
    intent: InvestigationIntent
    confidence: float
    rationale: str


_INTENT_SIGNALS: tuple[tuple[InvestigationIntent, tuple[str, ...]], ...] = (
    (InvestigationIntent.PRODUCTION_INVESTIGATION, ("production incident", "production issue", "prod incident", "live database evidence", "production support")),
    (InvestigationIntent.PERFORMANCE_INVESTIGATION, ("slow", "timeout", "performance", "full scan", "index", "explain", "long running")),
    (InvestigationIntent.DUPLICATE_DATA, ("duplicate", "double", "created twice", "two records", "two ", "multiple ", "idempot")),
    (InvestigationIntent.MISSING_DATA, ("missing", "not generated", "not created", "does not exist", "no row")),
    (InvestigationIntent.FAILED_BATCH_JOB, ("batch", "job failed", "failed step", "nightly", "scheduler")),
    (InvestigationIntent.RECONCILIATION_OR_MISMATCH, ("recon", "reconciliation", "mismatch", "out of balance", "does not match")),
    (InvestigationIntent.STORED_PROCEDURE_ANALYSIS, ("procedure", "stored proc", "sp_", "function")),
    (InvestigationIntent.IMPACT_ANALYSIS, ("impact", "affected", "blast radius", "after deployment", "what will break", "change status", "change values")),
    (InvestigationIntent.HEALTH_ASSESSMENT, ("health", "assessment", "score", "quality review", "database review")),
    (InvestigationIntent.TEST_CASE_GENERATION, ("test case", "test cases", "qa", "validate")),
    (InvestigationIntent.PROOF_OF_FIX, ("proof of fix", "prove fix", "acceptance", "verification")),
    (InvestigationIntent.PROCESS_FLOW_BREAK, ("flow", "process", "where broke", "trace", "lifecycle", "status")),
)


def detect_intent(question: str) -> IntentResult:
    lowered = question.lower()
    if "change" in lowered and any(term in lowered for term in ("status", "state", "value", "code")) and any(term in lowered for term in ("break", "impact", "affected", "risk")):
        return IntentResult(
            intent=InvestigationIntent.IMPACT_ANALYSIS,
            confidence=0.88,
            rationale="Change-impact wording detected around status/state/value/code semantics.",
        )
    primary_text = lowered
    for marker in (
        "group them by",
        "group by",
        "whether this is caused by",
        "possible causes",
        "for each group",
        "root cause:",
    ):
        if marker in primary_text:
            primary_text = primary_text.split(marker, 1)[0]
    scores: dict[InvestigationIntent, int] = {}
    for intent, signals in _INTENT_SIGNALS:
        score = sum(3 for signal in signals if signal in primary_text)
        score += sum(1 for signal in signals if signal in lowered and signal not in primary_text)
        if score:
            scores[intent] = score
    if not scores:
        return IntentResult(
            intent=InvestigationIntent.GENERAL_DATABASE_QUESTION,
            confidence=0.45,
            rationale="No strong incident signal found; treating as a general database question.",
        )
    priority = [
        InvestigationIntent.PRODUCTION_INVESTIGATION,
        InvestigationIntent.DUPLICATE_DATA,
        InvestigationIntent.MISSING_DATA,
        InvestigationIntent.PERFORMANCE_INVESTIGATION,
        InvestigationIntent.FAILED_BATCH_JOB,
        InvestigationIntent.RECONCILIATION_OR_MISMATCH,
        InvestigationIntent.PROCESS_FLOW_BREAK,
        InvestigationIntent.STORED_PROCEDURE_ANALYSIS,
        InvestigationIntent.IMPACT_ANALYSIS,
        InvestigationIntent.TEST_CASE_GENERATION,
        InvestigationIntent.PROOF_OF_FIX,
        InvestigationIntent.HEALTH_ASSESSMENT,
    ]
    selected = max(priority, key=lambda intent: (scores.get(intent, 0), -priority.index(intent)))
    matched_count = sum(1 for score in scores.values() if score > 0)
    return IntentResult(
        intent=selected,
        confidence=min(0.92, 0.55 + 0.08 * matched_count + 0.04 * scores.get(selected, 0)),
        rationale="Intent inferred from the primary request first, with secondary listed causes weighted lower.",
    )
