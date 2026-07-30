from __future__ import annotations

import pytest

from legacydb_copilot.workflow.langgraph.activation import (
    ComparisonCategory,
    OrchestrationResult,
    ReleaseDecision,
    ReleaseGateInput,
    compare_results,
    evaluate_release_gates,
)


def output(**metrics):
    return OrchestrationResult(payload=metrics.get("answer", "answer"), metrics=metrics)


def compare(left, right):
    return compare_results(left, right, correlation_id="correlation", selected_result="legacy")


def test_identical_results_match():
    metrics = {
        "answer": "Supported answer",
        "verified_evidence_count": 2,
        "coverage": 100,
        "terminal_status": "COMPLETE",
    }
    assert compare(output(**metrics), output(**metrics)).category is ComparisonCategory.MATCH


def test_equivalent_wording_is_equivalent():
    left = output(answer="alpha beta", verified_evidence_count=1)
    right = output(answer="beta alpha", verified_evidence_count=1)
    assert compare(left, right).category is ComparisonCategory.EQUIVALENT


def test_higher_graph_coverage_is_better():
    result = compare(
        output(answer="legacy", coverage=50, verified_evidence_count=1),
        output(answer="graph", coverage=100, verified_evidence_count=2),
    )
    assert result.category is ComparisonCategory.LANGGRAPH_BETTER


def test_lower_graph_verified_coverage_is_legacy_better():
    result = compare(
        output(answer="legacy", coverage=100, verified_evidence_count=2),
        output(answer="graph", coverage=50, verified_evidence_count=1),
    )
    assert result.category is ComparisonCategory.LEGACY_BETTER


@pytest.mark.parametrize(
    "critical",
    [
        {"null_semantics": "NULL"},
        {"authorization_ok": False},
        {"mutation_executed": True},
        {"stored_procedure_executed": True},
        {"unverified_evidence_to_llm": True},
    ],
)
def test_critical_safety_mismatch_blocks_regardless_of_score(critical):
    legacy = output(
        answer="same",
        null_semantics="NO_ROW" if "null_semantics" in critical else "",
        authorization_ok=True,
    )
    graph = output(
        answer="same",
        coverage=100,
        verified_evidence_count=10,
        **critical,
    )
    result = compare(legacy, graph)
    assert result.category is ComparisonCategory.BLOCKED
    assert result.scorecard["safety"] == 0
    assert result.release_blocking_findings


def test_token_cost_and_latency_differences_are_calculated():
    result = compare(
        output(answer="a", tokens=10, cost=0.1, latency_ms=50),
        output(answer="b", tokens=25, cost=0.3, latency_ms=80),
    )
    assert result.differences["tokens"] == 15
    assert result.differences["cost"] == pytest.approx(0.2)
    assert result.differences["latency_ms"] == 30


def test_missing_report_is_not_comparable():
    result = compare(output(answer=""), output(answer="graph"))
    assert result.category is ComparisonCategory.NOT_COMPARABLE


@pytest.mark.parametrize(
    "field",
    [
        "mutation_executed",
        "stored_procedure_executed",
        "authorization_violation",
        "unverified_evidence_to_llm",
        "fabricated_invocation",
        "secret_leakage",
        "unsupported_proof_of_fix",
    ],
)
def test_each_critical_release_gate_blocks(field):
    decision, reasons = evaluate_release_gates(
        ReleaseGateInput(
            regressions_passed=True,
            benchmark_passed=True,
            **{field: True},
        )
    )
    assert decision is ReleaseDecision.NOT_READY
    assert field in reasons


def test_environment_unavailable_is_explicit_blocker():
    decision, reasons = evaluate_release_gates(
        ReleaseGateInput(environment_available=False)
    )
    assert decision is ReleaseDecision.BLOCKED_BY_ENVIRONMENT
    assert reasons == ("live_environment_unavailable",)


def test_passing_non_live_gates_are_ready_with_conditions():
    decision, reasons = evaluate_release_gates(
        ReleaseGateInput(regressions_passed=True)
    )
    assert decision is ReleaseDecision.READY_WITH_CONDITIONS
    assert reasons == ("protected_benchmark_required",)


def test_all_release_gates_pass():
    decision, reasons = evaluate_release_gates(
        ReleaseGateInput(regressions_passed=True, benchmark_passed=True)
    )
    assert decision is ReleaseDecision.READY
    assert reasons == ()
