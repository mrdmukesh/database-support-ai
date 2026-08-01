from __future__ import annotations

import pytest

from legacydb_copilot.workflow.langgraph.adapters.reporting import ReportingAdapter
from legacydb_copilot.workflow.langgraph.enums import (
    EvidenceOutcome,
    WorkflowReasoningMode,
)
from legacydb_copilot.workflow.langgraph.state import (
    FindingRecord,
    create_initial_investigation_state,
)


def state(mode=WorkflowReasoningMode.NO_VERIFIED_EVIDENCE):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["reasoning_mode"] = mode
    value["verified_evidence_ids"] = ["EV-1"]
    return value


def deterministic(value):
    findings = [item.description for item in value["findings"]]
    return {
        "summary": "Verified evidence summary",
        "mode": value["reasoning_mode"].value,
        "findings": findings,
        "evidence_ids": value["verified_evidence_ids"],
        "gaps": [gap.description for gap in value["evidence_gaps"]],
        "llm_invoked": value["ai_reasoning_invoked"],
    }


def compose(value):
    return {
        "summary": "Reasoned report",
        "claims": value["reasoning_result"]["claims"],
        "evidence_ids": value["verified_evidence_ids"],
    }


@pytest.mark.parametrize(
    "mode",
    [
        WorkflowReasoningMode.NORMAL_ROOT_CAUSE,
        WorkflowReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
        WorkflowReasoningMode.INSUFFICIENT_EVIDENCE,
        WorkflowReasoningMode.NO_VERIFIED_EVIDENCE,
        WorkflowReasoningMode.NEEDS_HUMAN_REVIEW,
    ],
    ids=["TC-RP-01", "TC-RP-02", "TC-RP-03", "TC-RP-04", "TC-RP-05"],
)
def test_deterministic_modes(mode):
    assert (
        ReportingAdapter(compose, deterministic)(state(mode))["structured_report"]["mode"]
        == mode.value
    )


@pytest.mark.parametrize(
    ("outcome", "description"),
    [
        (EvidenceOutcome.REQUIRED_VALUE_MISSING, "DateOfBirth is NULL; age cannot be calculated."),
        (EvidenceOutcome.OPTIONAL_VALUE_NULL, "MiddleName is NULL."),
        (EvidenceOutcome.NO_MATCHING_ROW, "No matching employee record was verified."),
        (EvidenceOutcome.RELATIONSHIP_NOT_PRESENT, "Related Department was not verified."),
        (EvidenceOutcome.VALUE_PRESENT, "Mutating procedure inspected only; not executed."),
        (EvidenceOutcome.METADATA_INCOMPLETE, "Dynamic SQL dependency analysis is incomplete."),
        (EvidenceOutcome.QUERY_TIMED_OUT, "Query timed out."),
        (EvidenceOutcome.PERMISSION_BLOCKED, "Permission blocked required evidence."),
    ],
    ids=[
        "TC-RP-06",
        "TC-RP-07",
        "TC-RP-08",
        "TC-RP-09",
        "TC-RP-10",
        "TC-RP-11",
        "TC-RP-12",
        "TC-RP-13",
    ],
)
def test_finding_semantics_preserved(outcome, description):
    value = state()
    value["findings"] = [FindingRecord(finding_type=outcome, description=description)]
    report = ReportingAdapter(compose, deterministic)(value)["structured_report"]
    assert description.split()[0:3] == report["findings"][0].split()[0:3]


def test_tc_rp_14_provider_failure_fallback():
    value = state()
    value["deterministic_fallback_reason"] = "Provider timeout"
    assert ReportingAdapter(compose, deterministic)(value)["structured_report"]["summary"]


def test_tc_rp_15_no_provider_call_report():
    assert (
        ReportingAdapter(compose, deterministic)(state())["structured_report"]["llm_invoked"]
        is False
    )


def test_tc_rp_16_evidence_ids_preserved():
    assert ReportingAdapter(compose, deterministic)(state())["structured_report"][
        "evidence_ids"
    ] == ["EV-1"]


def test_tc_rp_17_reasoned_report_only_uses_persisted_valid_result():
    value = state(WorkflowReasoningMode.NORMAL_ROOT_CAUSE)
    value["reasoning_result"] = {"claims": [{"statement": "supported"}]}
    value["reasoning_persisted"] = True
    assert (
        ReportingAdapter(compose, deterministic)(value)["structured_report"]["summary"]
        == "Reasoned report"
    )


def test_tc_rp_18_secret_is_sanitized():
    report = ReportingAdapter(lambda _s: {}, lambda _s: {"password": "secret"})(state())
    assert "secret" not in str(report)
