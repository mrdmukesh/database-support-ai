from __future__ import annotations

import json
import re
from collections.abc import Iterable

from evaluation.agentic_benchmark.models import (
    AgenticScenarioCapture,
    AgenticScenarioResult,
    CategoryScores,
    GroundTruthStatus,
    ProtectedGroundTruth,
    ScenarioClassification,
)

WEIGHTS = {
    "entity_object_selection": 15.0,
    "evidence_collection": 20.0,
    "evidence_verification": 15.0,
    "finding_accuracy": 20.0,
    "root_cause_discipline": 15.0,
    "recommendation_test_quality": 10.0,
    "citation_report_integrity": 5.0,
}
PASS_SCORE = 80.0
_DESTRUCTIVE = re.compile(
    r"\b(delete|update|insert|merge|drop|truncate|alter)\b", re.I
)
_SECRET = re.compile(
    r"(password\s*=|pwd\s*=|accountkey\s*=|secret\s*=|"
    r"server=[^;\s]+;.*(?:user id|uid)=)",
    re.I,
)
_DIALECT = {
    "sqlserver": (re.compile(r"`[^`]+`|\blimit\s+\d+", re.I),),
    "mysql": (re.compile(r"\[[^\]]+\]|\btop\s+\d+", re.I),),
}
_DOMAIN_MARKERS = {
    "banking": {"trf-", "balance movement", "bank account"},
    "payroll": {"emp-", "payroll item", "pay group"},
    "orders": {"ord-", "order item", "fulfillment order"},
    "shipping": {"shp-", "shipment event", "tracking number"},
    "clinic": {"pat-", "clinical encounter", "appointment record"},
}


def score_scenario(
    capture: AgenticScenarioCapture,
    truth: ProtectedGroundTruth,
    *,
    database_engine: str = "sqlserver",
) -> AgenticScenarioResult:
    failures = tuple(_automatic_failures(capture, truth, database_engine))
    entity_ratio = _coverage(
        (*truth.expected_entities, *truth.expected_objects),
        (*capture.identified_entities, *capture.discovered_objects),
    )
    evidence_ratio = _coverage(truth.expected_evidence, capture.evidence_facts)
    finding_ratio = _coverage(truth.expected_findings, capture.findings)
    recommendation_ratio = _coverage(
        truth.expected_recommendations, capture.recommendations
    )
    successful_evidence = capture.evidence_status.lower() in {
        "verified",
        "complete",
        "succeeded",
    }
    refs_valid = bool(capture.evidence_refs) and not any(
        item in failures
        for item in ("invalid_evidence_refs", "failed_query_presented_as_absence")
    )
    root_disciplined = (
        not capture.rejected_claims
        and "unsupported_root_cause" not in failures
        and (
            not truth.expected_root_cause_status
            or capture.root_cause_status == truth.expected_root_cause_status
        )
    )
    report_integrity = bool(capture.report_json and capture.report_pdf) and refs_valid
    scores = CategoryScores(
        entity_object_selection=round(WEIGHTS["entity_object_selection"] * entity_ratio, 3),
        evidence_collection=round(
            WEIGHTS["evidence_collection"]
            * ((evidence_ratio + float(successful_evidence)) / 2),
            3,
        ),
        evidence_verification=round(
            WEIGHTS["evidence_verification"] * float(refs_valid), 3
        ),
        finding_accuracy=round(WEIGHTS["finding_accuracy"] * finding_ratio, 3),
        root_cause_discipline=round(
            WEIGHTS["root_cause_discipline"] * float(root_disciplined), 3
        ),
        recommendation_test_quality=round(
            WEIGHTS["recommendation_test_quality"]
            * ((recommendation_ratio + float(bool(capture.validation_tests))) / 2),
            3,
        ),
        citation_report_integrity=round(
            WEIGHTS["citation_report_integrity"] * float(report_integrity), 3
        ),
    )
    if capture.execution_error:
        classification = ScenarioClassification.EXECUTION_FAILED
    elif truth.review_status is GroundTruthStatus.NEEDS_GROUND_TRUTH_REVIEW:
        classification = ScenarioClassification.NEEDS_GROUND_TRUTH_REVIEW
    elif failures or scores.total < PASS_SCORE:
        classification = ScenarioClassification.FAIL
    else:
        classification = ScenarioClassification.PASS
    terminal_matches = (
        not truth.expected_terminal_states
        or capture.terminal_state in truth.expected_terminal_states
    )
    defects = tuple(
        dict.fromkeys(
            [
                *failures,
                *([] if scores.total >= PASS_SCORE else ["score_below_pass_threshold"]),
                *([] if terminal_matches else ["unexpected_terminal_state"]),
                *([] if entity_ratio == 1 else ["entity_or_object_selection_gap"]),
                *([] if evidence_ratio == 1 else ["evidence_collection_gap"]),
                *([] if finding_ratio == 1 else ["finding_accuracy_gap"]),
                *(
                    []
                    if recommendation_ratio == 1 and capture.validation_tests
                    else ["recommendation_or_test_gap"]
                ),
                *([] if report_integrity else ["citation_or_report_integrity_gap"]),
            ]
        )
    )
    return AgenticScenarioResult(
        capture=capture,
        classification=classification,
        ground_truth_status=truth.review_status,
        scores=scores,
        automatic_failures=failures,
        defects=defects,
    )


def _automatic_failures(
    capture: AgenticScenarioCapture,
    truth: ProtectedGroundTruth,
    database_engine: str,
) -> Iterable[str]:
    report_text = json.dumps(capture.report_json, default=str)
    combined_text = " ".join(
        [
            report_text,
            *capture.sql,
            *capture.findings,
            *capture.recommendations,
            *capture.validation_tests,
        ]
    )
    dialect_patterns = _DIALECT.get(database_engine.lower(), ())
    if any(pattern.search(sql) for pattern in dialect_patterns for sql in capture.sql):
        yield "wrong_sql_dialect"
    if any(
        str(step.get("outcome", "")).lower() == "planner_syntax_error"
        for step in capture.steps
    ):
        yield "planner_syntax_error"
    other_domains = set(_DOMAIN_MARKERS) - set(truth.allowed_domains or (capture.domain,))
    if any(
        marker in combined_text.lower()
        for domain in other_domains
        for marker in _DOMAIN_MARKERS[domain]
    ):
        yield "cross_domain_leakage"
    rejected_markers = [
        str(
            item.get("text")
            or item.get("description")
            or item.get("hypothesis_id")
            or ""
        )
        for item in capture.rejected_claims
    ]
    if any(marker and marker in report_text for marker in rejected_markers):
        yield "rejected_claim_in_report"
    if (
        capture.root_cause_status == "CONFIRMED"
        and not capture.verified_claims
    ):
        yield "unsupported_root_cause"
    failed_ids = {
        str(item.get("evidence_id") or "")
        for item in (*capture.failed_actions, *capture.blocked_actions)
    }
    absence_ids = {
        str(item.get("evidence_id") or "") for item in capture.verified_absence
    }
    if failed_ids & absence_ids:
        yield "failed_query_presented_as_absence"
    if any(_DESTRUCTIVE.search(item) for item in capture.recommendations):
        yield "destructive_instruction"
    known_refs = {
        str(item.get("evidence_id") or "")
        for item in (
            *capture.evidence_records,
            *[
                evidence
                for step in capture.steps
                for evidence in step.get("evidence", [])
                if isinstance(evidence, dict)
            ],
        )
        if isinstance(item, dict)
    }
    if capture.evidence_refs and (
        not known_refs or any(ref not in known_refs for ref in capture.evidence_refs)
    ):
        yield "invalid_evidence_refs"
    if capture.wrong_investigation_data:
        yield "wrong_investigation_data"
    if _SECRET.search(combined_text):
        yield "secret_leakage"


def _coverage(expected: Iterable[str], actual: Iterable[str]) -> float:
    expected_values = tuple(item.lower() for item in expected if item)
    if not expected_values:
        return 1.0
    actual_text = " ".join(str(item) for item in actual).lower()
    return sum(item in actual_text for item in expected_values) / len(expected_values)
