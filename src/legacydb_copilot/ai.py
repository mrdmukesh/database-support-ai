from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


AI_DISCLAIMER_POINTS = (
    "AI-generated responses are recommendations only.",
    "Always validate SQL before executing.",
    "Production changes require human approval.",
    "Confidence score is an estimate.",
    "Answers are generated using uploaded documentation and extracted database metadata.",
    "AI may be incorrect.",
    "This product does not replace DBAs or senior developers.",
)


class SafetyFinding(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    UNSAFE_SQL = "unsafe_sql"
    HALLUCINATION_RISK = "hallucination_risk"


@dataclass(frozen=True)
class SafetyReport:
    findings: tuple[SafetyFinding, ...]
    confidence: float
    requires_human_review: bool

    @property
    def is_safe(self) -> bool:
        return not self.findings


PROMPT_INJECTION_PATTERNS = (
    re.compile(r"ignore (all )?(previous|prior) instructions", re.I),
    re.compile(r"reveal (system|developer|hidden) prompt", re.I),
    re.compile(r"bypass (security|policy|guardrails)", re.I),
)

UNSAFE_SQL_PATTERNS = (
    re.compile(r"\b(drop|truncate)\s+(database|schema|table)\b", re.I),
    re.compile(r"\bdelete\s+from\b(?![\s\S]*\bwhere\b)", re.I),
    re.compile(r"\bupdate\b[\s\S]+\bset\b(?![\s\S]*\bwhere\b)", re.I),
    re.compile(r"\bexec(ute)?\s+xp_cmdshell\b", re.I),
)


def disclaimer_text() -> str:
    return "\n".join(f"- {point}" for point in AI_DISCLAIMER_POINTS)


def analyze_prompt(prompt: str, *, has_sources: bool = True) -> SafetyReport:
    findings: list[SafetyFinding] = []
    if any(pattern.search(prompt) for pattern in PROMPT_INJECTION_PATTERNS):
        findings.append(SafetyFinding.PROMPT_INJECTION)
    if any(pattern.search(prompt) for pattern in UNSAFE_SQL_PATTERNS):
        findings.append(SafetyFinding.UNSAFE_SQL)
    if not has_sources:
        findings.append(SafetyFinding.HALLUCINATION_RISK)

    confidence = max(0.05, 1.0 - (0.28 * len(findings)))
    return SafetyReport(
        findings=tuple(dict.fromkeys(findings)),
        confidence=round(confidence, 2),
        requires_human_review=bool(findings),
    )
