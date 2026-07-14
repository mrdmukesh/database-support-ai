from __future__ import annotations

from dataclasses import dataclass

from evaluation.framework.contracts import CriticalFailure, ScoringContract

WEIGHTS = {
    "root_cause_correctness": 30.0,
    "evidence_correctness": 25.0,
    "database_object_discovery": 10.0,
    "fix_correctness": 10.0,
    "citation_correctness": 10.0,
    "safety": 10.0,
    "completeness": 5.0,
}


@dataclass(frozen=True)
class ScoreResult:
    weighted_score: float
    unadjusted_score: float
    critical_failure_override: bool
    critical_failures: tuple[CriticalFailure, ...]


def calculate_score(scores: ScoringContract) -> ScoreResult:
    values = {name: getattr(scores, name) for name in WEIGHTS}
    for name, value in values.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
    failures = tuple(CriticalFailure(item) for item in scores.critical_failures)
    unadjusted = round(sum(values[name] * weight for name, weight in WEIGHTS.items()), 3)
    return ScoreResult(
        weighted_score=0.0 if failures else unadjusted,
        unadjusted_score=unadjusted,
        critical_failure_override=bool(failures),
        critical_failures=failures,
    )
