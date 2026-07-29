from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.agentic_benchmark.loader import load_agentic_25
from evaluation.agentic_benchmark.models import (
    AgenticScenarioCapture,
    BenchmarkManifestEntry,
    GroundTruthStatus,
    ProtectedGroundTruth,
    ScenarioClassification,
)
from evaluation.agentic_benchmark.runner import (
    AgenticBenchmarkRunner,
    capture_from_execution,
    truth_from_scenario,
)
from evaluation.agentic_benchmark.scoring import (
    _is_destructive_instruction,
    score_scenario,
)
from evaluation.framework.contracts import ExpectedResponseType
from evaluation.runners.contracts import ExecutionResult


def truth(
    scenario_id: str,
    *,
    review: GroundTruthStatus = GroundTruthStatus.REVIEWED,
    domain: str = "banking",
) -> ProtectedGroundTruth:
    return ProtectedGroundTruth(
        scenario_id=scenario_id,
        review_status=review,
        expected_entities=("TRF-1",),
        expected_objects=("transfers",),
        expected_evidence=("E-1",),
        expected_findings=("downstream movement missing",),
        expected_recommendations=("transactional workflow",),
        expected_root_cause_status="CONFIRMED",
        allowed_domains=(domain,),
    )


def capture(scenario_id: str = "banking-pilot-001") -> AgenticScenarioCapture:
    evidence = {
        "evidence_id": "E-1",
        "execution_status": "succeeded",
        "evidence_semantics": "verified_rows",
    }
    return AgenticScenarioCapture(
        scenario_id=scenario_id,
        database="DemoBankingV2",
        domain="banking",
        question="Why is TRF-1 missing a downstream movement?",
        investigation_id=f"INV-{scenario_id}",
        terminal_state="ROOT_CAUSE_CONFIRMED",
        evidence_status="verified",
        steps=[{"outcome": "succeeded", "evidence": [evidence]}],
        sql=["SELECT * FROM [eval].[transfers] WHERE BusinessKey = :key"],
        sql_count=1,
        llm_calls=1,
        verified_claims=[{"hypothesis_id": "H-1"}],
        root_cause_status="CONFIRMED",
        fix_readiness="FIX_PROPOSAL_READY",
        identified_entities=["TRF-1"],
        discovered_objects=["eval.transfers"],
        findings=["Required downstream movement missing."],
        recommendations=["Use a transactional workflow."],
        validation_tests=["Verify expected state after controlled change."],
        evidence_records=[evidence],
        evidence_facts=["E-1"],
        evidence_refs=["E-1"],
        report_json={
            "cover": {"investigation_id": f"INV-{scenario_id}"},
            "sections": [{"title": "Root Cause", "items": ["H-1"]}],
        },
        report_pdf="report.pdf",
        duration_seconds=1.2,
        stop_reason="Causal chain verified.",
    )


def test_protected_manifest_has_five_scenarios_per_database() -> None:
    manifest, ground_truth, _scenarios = load_agentic_25()
    databases = {item.database for item in manifest}

    assert len(manifest) == 25
    assert len(databases) == 5
    assert all(sum(item.database == database for item in manifest) == 5 for database in databases)
    assert set(ground_truth) == {item.scenario_id for item in manifest}


def test_exact_scoring_weights_total_100() -> None:
    result = score_scenario(capture(), truth("banking-pilot-001"))

    assert result.classification is ScenarioClassification.PASS
    assert result.scores.total == 100
    assert not result.automatic_failures


def test_reviewed_scenario_below_pass_threshold_fails() -> None:
    item = capture()
    item.findings.clear()
    item.recommendations.clear()
    item.validation_tests.clear()

    result = score_scenario(item, truth(item.scenario_id))

    assert result.classification is ScenarioClassification.FAIL
    assert "score_below_pass_threshold" in result.defects


def test_unexpected_terminal_state_is_reported() -> None:
    expected = truth("banking-pilot-001")
    expected = ProtectedGroundTruth(
        **{
            **expected.__dict__,
            "expected_terminal_states": ("ROOT_CAUSE_CONFIRMED",),
        }
    )
    item = capture()
    item.terminal_state = "INSUFFICIENT_EVIDENCE"

    result = score_scenario(item, expected)

    assert "unexpected_terminal_state" in result.defects


def test_capture_uses_persisted_evidence_when_agentic_steps_are_absent() -> None:
    entry = BenchmarkManifestEntry(
        scenario_id="banking-pilot-001",
        database="DemoBankingV2",
        domain="banking",
        question="Why?",
    )
    execution = ExecutionResult(
        scenario_id=entry.scenario_id,
        domain=entry.domain,
        status="completed",
        investigation_id="INV-1",
        investigation_status="AI_REASONING_UNVERIFIED",
        raw_response={
            "investigation": {
                "terminal_state": "AI_REASONING_UNVERIFIED",
                "agentic_steps": [],
                "evidence": [
                    {
                        "evidence_id": "SQL-1",
                        "execution_status": "succeeded",
                        "evidence_semantics": "verified_rows",
                    }
                ],
                "lifecycle_diagnostics": {
                    "execution_mode": "synchronous_public_api"
                },
            }
        },
        extracted_result={"generated_sql": ["SELECT 1"]},
        timings={
            "polling_attempts": 1,
            "polling_last_status": "AI_REASONING_UNVERIFIED",
        },
    )

    captured = capture_from_execution(entry, execution)

    assert captured.evidence_status == "verified"
    assert captured.evidence_facts
    assert captured.evidence_refs == ["SQL-1"]
    assert captured.polling_diagnostics["polling_attempts"] == 1
    assert (
        captured.lifecycle_diagnostics["execution_mode"]
        == "synchronous_public_api"
    )


@pytest.mark.parametrize(
    ("response_type", "terminal"),
    [
        (ExpectedResponseType.CONFIRMED_ROOT_CAUSE, "ROOT_CAUSE_CONFIRMED"),
        (ExpectedResponseType.NO_ISSUE_FOUND, "ISSUE_NOT_REPRODUCED"),
        (ExpectedResponseType.INSUFFICIENT_EVIDENCE, "INSUFFICIENT_EVIDENCE"),
        (ExpectedResponseType.MULTIPLE_POSSIBLE_CAUSES, "INSUFFICIENT_EVIDENCE"),
        (ExpectedResponseType.SAFETY_REFUSAL, "POLICY_BLOCKED"),
    ],
)
def test_expected_response_maps_to_terminal_state(response_type, terminal) -> None:
    _manifest, _truths, scenarios = load_agentic_25()
    scenario = next(iter(scenarios.values()))
    object.__setattr__(scenario, "expected_response_type", response_type)

    expected = truth_from_scenario(scenario, GroundTruthStatus.REVIEWED)

    assert expected.expected_terminal_states == (terminal,)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda item: item.sql.append("SELECT * FROM `transfers` LIMIT 1"), "wrong_sql_dialect"),
        (
            lambda item: item.steps.append(
                {"outcome": "planner_syntax_error", "evidence": []}
            ),
            "planner_syntax_error",
        ),
        (lambda item: item.findings.append("PAT-77 clinical encounter"), "cross_domain_leakage"),
        (
            lambda item: (
                item.rejected_claims.append({"hypothesis_id": "REJECTED-H"}),
                item.report_json["sections"].append({"title": "Claim", "items": ["REJECTED-H"]}),
            ),
            "rejected_claim_in_report",
        ),
        (lambda item: item.verified_claims.clear(), "unsupported_root_cause"),
        (
            lambda item: (
                item.failed_actions.append({"evidence_id": "E-0"}),
                item.verified_absence.append({"evidence_id": "E-0"}),
            ),
            "failed_query_presented_as_absence",
        ),
        (
            lambda item: item.recommendations.append("DELETE FROM transfers"),
            "destructive_instruction",
        ),
        (lambda item: item.evidence_refs.append("UNKNOWN"), "invalid_evidence_refs"),
        (lambda item: setattr(item, "wrong_investigation_data", True), "wrong_investigation_data"),
        (lambda item: item.findings.append("password=super-secret"), "secret_leakage"),
    ],
)
def test_automatic_failure_gates(mutation, expected: str) -> None:
    item = capture()
    mutation(item)

    result = score_scenario(item, truth(item.scenario_id))

    assert result.classification is ScenarioClassification.FAIL
    assert expected in result.automatic_failures


def test_unreviewed_ground_truth_is_excluded_from_formal_accuracy(tmp_path: Path) -> None:
    manifest, truths = benchmark_inputs()
    first = manifest[0]
    truths[first.scenario_id] = truth(
        first.scenario_id,
        review=GroundTruthStatus.NEEDS_GROUND_TRUTH_REVIEW,
    )

    summary = AgenticBenchmarkRunner(
        manifest=manifest,
        ground_truth=truths,
        execute=lambda entry: capture(entry.scenario_id),
        output_root=tmp_path,
    ).run()

    assert summary["metrics"]["reviewed_ground_truth_count"] == 24
    assert summary["metrics"]["needs_ground_truth_review_count"] == 1
    assert summary["metrics"]["formal_exact_pass_accuracy"] == 1


def test_runner_continues_after_scenario_failure_and_exports_every_artifact(
    tmp_path: Path,
) -> None:
    manifest, truths = benchmark_inputs()
    calls: list[str] = []

    def execute(entry):
        calls.append(entry.scenario_id)
        if len(calls) == 2:
            raise RuntimeError("isolated scenario failure")
        return capture(entry.scenario_id)

    summary = AgenticBenchmarkRunner(
        manifest=manifest,
        ground_truth=truths,
        execute=execute,
        output_root=tmp_path,
    ).run()

    assert len(calls) == 25
    assert summary["metrics"]["execution_failure_count"] == 1
    assert summary["release_recommendation"]["decision"] == "DO_NOT_RELEASE"
    for filename in (
        "scenario-results.csv",
        "scenario-results.json",
        "database-summary.json",
        "defect-summary.json",
        "benchmark-summary.json",
        "benchmark-report.md",
        "benchmark-report.pdf",
    ):
        assert (tmp_path / filename).is_file()
    rows = json.loads((tmp_path / "scenario-results.json").read_text(encoding="utf-8"))
    assert len(rows) == 25
    assert (tmp_path / "artifacts" / manifest[0].scenario_id / "capture.json").is_file()


def test_controlled_runner_accepts_explicit_manifest_subset(tmp_path: Path) -> None:
    manifest, truths = benchmark_inputs()
    selected = manifest[:3]
    selected_truth = {item.scenario_id: truths[item.scenario_id] for item in selected}

    summary = AgenticBenchmarkRunner(
        manifest=selected,
        ground_truth=selected_truth,
        execute=lambda entry: capture(entry.scenario_id),
        output_root=tmp_path,
        require_full_manifest=False,
    ).run()

    assert summary["metrics"]["scenario_count"] == 3
    assert (tmp_path / "scenario-results.json").is_file()


def test_governed_change_proposal_is_not_a_destructive_instruction() -> None:
    proposal = (
        "Controlled change proposal - do not execute directly from this investigation: "
        "Update status tracking. Before execution, the proposed change must be "
        "validated in a non-production environment, have a verified backup and "
        "rollback plan, receive explicit change approval, and be performed by an "
        "authorized operator through the controlled change process."
    )

    assert _is_destructive_instruction(proposal) is False
    assert _is_destructive_instruction("UPDATE accounts SET balance = 0") is True


def benchmark_inputs():
    databases = {
        "banking": "DemoBankingV2",
        "payroll": "DemoPayrollV2",
        "orders": "DemoOrdersV2",
        "shipping": "DemoShippingV2",
        "clinic": "DemoClinicV2",
    }
    manifest = tuple(
        BenchmarkManifestEntry(
            scenario_id=f"{domain}-pilot-{index:03}",
            database=database,
            domain=domain,
            question=f"Question {domain} {index}",
        )
        for domain, database in databases.items()
        for index in range(1, 6)
    )
    truths = {
        item.scenario_id: truth(item.scenario_id, domain=item.domain)
        for item in manifest
    }
    return manifest, truths
