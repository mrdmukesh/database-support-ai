from __future__ import annotations

import pytest

from evaluation.agentic_benchmark.models import (
    BenchmarkManifestEntry,
    GroundTruthStatus,
    ProtectedGroundTruth,
)
from evaluation.agentic_benchmark.runner import (
    _result_row,
    capture_from_execution,
)
from evaluation.agentic_benchmark.scoring import score_scenario
from evaluation.runners.contracts import ExecutionResult
from evaluation.runners.runner import EvaluationRunner


def _entry() -> BenchmarkManifestEntry:
    return BenchmarkManifestEntry(
        scenario_id="generic-capture-001",
        database="DemoInventoryV2",
        domain="inventory",
        question="Why did the requested workflow produce an unexpected state?",
    )


def _confirmed_fact_report(*extra_sections: dict) -> dict:
    return {
        "cover": {"investigation_id": "INV-GENERIC-1"},
        "sections": [
            {
                "title": "Facts, Inferences, and Hypotheses",
                "tables": [
                    {
                        "title": "Reasoning Separation",
                        "columns": ["Type", "Finding"],
                        "rows": [
                            {
                                "Type": "Confirmed Fact",
                                "Finding": "The requested workflow row is in Exception state.",
                            },
                            {
                                "Type": "Inference",
                                "Finding": "A retry may have occurred.",
                            },
                            {
                                "Type": "Hypothesis",
                                "Finding": "A downstream component may have failed.",
                            },
                        ],
                    }
                ],
                "items": [],
                "paragraphs": [],
                "sql_blocks": [],
            },
            *extra_sections,
        ],
    }


def _execution(
    *,
    validated_citations: list[dict] | None = None,
    rejected_claims: list[dict] | None = None,
    ag_hypotheses: list[dict] | None = None,
    report: dict | None = None,
) -> ExecutionResult:
    detail = {
        "status": "AI_ANSWERED",
        "terminal_state": "AI_ANSWERED",
        "agentic_steps": [],
        "evidence": [
            {
                "evidence_id": "SQL-1",
                "execution_status": "succeeded",
                "evidence_semantics": "positive_rows",
                "row_count": 1,
            }
        ],
        "root_cause_verifications": ag_hypotheses or [],
        "debug_trace": {
            "llm_invoked": True,
            "validated_citations": validated_citations or [],
            "rejected_or_unsupported_claims": rejected_claims or [],
        },
        "report_json": report or {"cover": {}, "sections": []},
        "report_snapshot": report or {"cover": {}, "sections": []},
    }
    execution = ExecutionResult(
        scenario_id=_entry().scenario_id,
        domain=_entry().domain,
        status="completed",
        investigation_id="INV-GENERIC-1",
        investigation_status="AI_ANSWERED",
        raw_response={"investigation": detail},
        timings={"total_seconds": 1.0},
    )
    execution.extracted_result = EvaluationRunner._extract({}, detail)
    return execution


def _accepted_claim(
    claim_id: str = "CL-001",
    text: str = "The workflow row is in Exception state.",
) -> dict:
    return {
        "claim_id": claim_id,
        "claim": text,
        "evidence_refs": ["SQL-1"],
    }


def _ag_claim(
    hypothesis_id: str = "AG-CLAIM-001",
    text: str = "The persisted hypothesis is confirmed.",
) -> dict:
    return {
        "hypothesis_id": hypothesis_id,
        "claim": text,
        "origin": "DETERMINISTIC",
        "status": "CONFIRMED",
        "valid_evidence_refs": ["SQL-1"],
        "visible_in_report": True,
    }


def _result_counts(captured) -> dict:
    truth = ProtectedGroundTruth(
        scenario_id=captured.scenario_id,
        review_status=GroundTruthStatus.REVIEWED,
    )
    return _result_row(score_scenario(captured, truth))


def test_verified_synchronous_llm_claim_is_captured() -> None:
    captured = capture_from_execution(
        _entry(),
        _execution(validated_citations=[_accepted_claim()]),
    )
    counts = _result_counts(captured)

    assert captured.verified_claims == [_accepted_claim()]
    assert counts["verified_claim_count"] == 1


def test_ag_and_synchronous_verified_claims_are_merged() -> None:
    ag_claim = _ag_claim()
    synchronous_claim = _accepted_claim()

    captured = capture_from_execution(
        _entry(),
        _execution(
            ag_hypotheses=[ag_claim],
            validated_citations=[synchronous_claim],
        ),
    )

    assert captured.verified_claims == [ag_claim, synchronous_claim]
    assert _result_counts(captured)["verified_claim_count"] == 2


@pytest.mark.parametrize(
    ("ag_claim", "synchronous_claim"),
    [
        (
            _ag_claim("SHARED-001", "The workflow row is in Exception state."),
            _accepted_claim("SHARED-001", "The workflow row is in Exception state."),
        ),
        (
            _ag_claim("", "  The workflow ROW is in exception state. "),
            _accepted_claim("", "the workflow row is in Exception state"),
        ),
    ],
)
def test_duplicate_verified_claim_is_counted_once(
    ag_claim: dict,
    synchronous_claim: dict,
) -> None:
    captured = capture_from_execution(
        _entry(),
        _execution(
            ag_hypotheses=[ag_claim],
            validated_citations=[synchronous_claim],
        ),
    )

    assert len(captured.verified_claims) == 1
    assert _result_counts(captured)["verified_claim_count"] == 1


def test_rejected_siblings_do_not_remove_verified_claim() -> None:
    rejected = [
        {
            "claim_id": "CL-002",
            "claim": "A missing row can be asserted.",
            "reason": "unverified_negative_evidence",
        },
        {
            "claim_id": "CL-003",
            "claim": "An uncited external event occurred.",
            "reason": "missing_evidence_refs",
        },
    ]

    captured = capture_from_execution(
        _entry(),
        _execution(
            validated_citations=[_accepted_claim()],
            rejected_claims=rejected,
        ),
    )

    assert captured.verified_claims == [_accepted_claim()]
    assert captured.rejected_claims == rejected


def test_only_confirmed_fact_rows_become_findings() -> None:
    captured = capture_from_execution(
        _entry(),
        _execution(report=_confirmed_fact_report()),
    )

    assert captured.findings == [
        "The requested workflow row is in Exception state."
    ]


def test_unsupported_report_sections_are_not_findings() -> None:
    unsupported = [
        {
            "title": "Recommendations",
            "items": ["Apply an unverified recommendation."],
        },
        {
            "title": "Missing Evidence",
            "items": ["An external event log is unavailable."],
        },
        {
            "title": "General Analysis",
            "paragraphs": ["Generic narrative must not become a finding."],
        },
    ]
    captured = capture_from_execution(
        _entry(),
        _execution(report=_confirmed_fact_report(*unsupported)),
    )

    combined = " ".join(captured.findings)
    assert "recommendation" not in combined.casefold()
    assert "external event log" not in combined.casefold()
    assert "generic narrative" not in combined.casefold()
    assert "retry may have occurred" not in combined.casefold()
    assert "downstream component may have failed" not in combined.casefold()


def test_capture_counts_are_internally_consistent() -> None:
    rejected = [
        {"claim_id": "CL-002", "claim": "Rejected one", "reason": "missing_evidence_refs"},
        {"claim_id": "CL-003", "claim": "Rejected two", "reason": "missing_evidence_refs"},
    ]
    captured = capture_from_execution(
        _entry(),
        _execution(
            validated_citations=[_accepted_claim()],
            rejected_claims=rejected,
            report=_confirmed_fact_report(),
        ),
    )
    counts = _result_counts(captured)

    assert counts["verified_claim_count"] == len(captured.verified_claims) == 1
    assert counts["rejected_claim_count"] == len(captured.rejected_claims) == 2
    assert len(captured.findings) == 1


def test_existing_ag_only_verified_claim_behavior_is_preserved() -> None:
    ag_claim = _ag_claim()

    captured = capture_from_execution(
        _entry(),
        _execution(ag_hypotheses=[ag_claim]),
    )

    assert captured.verified_claims == [ag_claim]
    assert _result_counts(captured)["verified_claim_count"] == 1
