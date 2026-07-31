from __future__ import annotations

from typing import Any

from evaluation.accuracy.contracts import AccuracyValidationResult


def build_accuracy_report(
    validation: AccuracyValidationResult,
    investigation: dict[str, Any],
) -> dict[str, Any]:
    """Build a portable JSON report from deterministic validation output."""
    timing = investigation.get("timing") or {}
    usage = investigation.get("usage") or {}
    duration = timing.get("total_seconds")
    return {
        "report_version": "accuracy-v1",
        "scenario_id": validation.scenario_id,
        "deterministic_score": validation.deterministic_score,
        "component_scores": validation.component_scores,
        "automatic_failure": validation.automatic_failure,
        "failure_reasons": list(validation.failure_reasons),
        "unsupported_claims": list(validation.unsupported_claims),
        "hallucination_detection": {
            "passed": not validation.hallucination_findings,
            "findings": list(validation.hallucination_findings),
        },
        "evidence_coverage_percent": validation.evidence_coverage,
        "sql_coverage_percent": validation.sql_coverage,
        "investigation_duration_seconds": (
            float(duration) if duration is not None else None
        ),
        "token_usage": {
            name: _optional_int(usage.get(name))
            for name in (
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "total_tokens",
            )
        },
        "model_used": usage.get("model") or investigation.get("model"),
        "checks": validation.checks,
        "pass_fail_recommendation": validation.recommendation,
        "thresholds": {
            "development": {"minimum_score": 70, "automatic_failures_allowed": 0},
            "uat": {"minimum_score": 85, "automatic_failures_allowed": 0},
            "production": {
                "minimum_score": 92,
                "automatic_failures_allowed": 0,
                "minimum_evidence_coverage_percent": 90,
                "minimum_sql_coverage_percent": 90,
            },
        },
    }


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None
