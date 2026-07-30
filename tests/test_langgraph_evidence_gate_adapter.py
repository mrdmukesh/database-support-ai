from __future__ import annotations

from datetime import UTC, datetime

from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult
from legacydb_copilot.workflow.langgraph.adapters.evidence_gate import EvidenceGateAdapter
from legacydb_copilot.workflow.langgraph.enums import (
    CoverageStatus,
    WorkflowReasoningMode,
)
from legacydb_copilot.workflow.langgraph.state import (
    EvidenceGapRecord,
    create_initial_investigation_state,
)


def state(ids=("EV-1",), coverage=CoverageStatus.COMPLETE):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["verified_evidence_ids"] = list(ids)
    value["coverage_status"] = coverage
    return value


def gate(*, reproduced=True, verified=1):
    return EvidenceGateResult(
        required=True,
        reproduced=reproduced,
        business_key_exists=True,
        reported_condition_exists=reproduced,
        affected_rows_exist=True,
        parent_child_relationship_exists=True,
        confirmed_facts=["fact"],
        blocking_reasons=[] if reproduced else ["not reproduced"],
        missing_evidence=[] if reproduced else ["condition"],
        status_interpretation=[],
        verified_evidence=bool(verified),
        reasoning_permission="ALLOW_REASONING" if verified else "DENY_REASONING",
        permission_reason="verified" if verified else "none",
        verified_evidence_count=verified,
        evidence_categories=["positive_rows"] if verified else [],
    )


def apply(value, result):
    return EvidenceGateAdapter(lambda _state, _ids: result)(value)


def test_tc_eg_01_reproduced_allows_provider():
    output = apply(state(), gate())
    assert output["provider_call_required"]
    assert output["reasoning_mode"] == WorkflowReasoningMode.NORMAL_ROOT_CAUSE


def test_tc_eg_02_not_reproduced_summary_mode():
    assert (
        apply(state(), gate(reproduced=False))["reasoning_mode"]
        == WorkflowReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED
    )


def test_tc_eg_03_partial_coverage_is_insufficient():
    output = apply(state(coverage=CoverageStatus.PARTIAL), gate())
    assert output["reasoning_mode"] == WorkflowReasoningMode.INSUFFICIENT_EVIDENCE
    assert not output["provider_call_required"]


def test_tc_eg_04_no_verified_evidence_skips_provider():
    output = apply(state(()), gate(verified=0))
    assert output["reasoning_mode"] == WorkflowReasoningMode.NO_VERIFIED_EVIDENCE
    assert not output["provider_call_required"]


def test_tc_eg_05_persistence_failure_blocks():
    value = state()
    from legacydb_copilot.workflow.langgraph.state import ErrorRecord

    value["errors"] = [
        ErrorRecord(
            source_node="e",
            code="EVIDENCE_PERSISTENCE_FAILED",
            message="failed",
            timestamp=datetime.now(UTC),
        )
    ]
    assert not apply(value, gate())["provider_call_required"]


def test_tc_eg_06_dynamic_sql_needs_review():
    value = state()
    value["metadata_gaps"] = [
        EvidenceGapRecord(
            gap_type="dynamic_sql",
            description="Dynamic SQL dependencies incomplete",
            blocking=True,
            source_node="discover",
            timestamp=datetime.now(UTC),
        )
    ]
    assert apply(value, gate())["reasoning_mode"] == WorkflowReasoningMode.NEEDS_HUMAN_REVIEW


def test_tc_eg_07_cancelled_never_calls_gate():
    value = state()
    value["cancel_requested"] = True
    calls = []
    output = EvidenceGateAdapter(lambda *_args: calls.append(True))(value)
    assert calls == [] and not output["provider_call_required"]


def test_tc_eg_08_skip_reason_without_invocation():
    output = apply(state(()), gate(verified=0))
    assert output["llm_skip_reason"] and output["provider_call_required"] is False
