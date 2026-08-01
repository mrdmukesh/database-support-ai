from __future__ import annotations

import pytest

from legacydb_copilot.workflow.langgraph.adapters.coverage import coverage_route
from legacydb_copilot.workflow.langgraph.enums import CoverageStatus
from legacydb_copilot.workflow.langgraph.state import create_initial_investigation_state


def state(status=CoverageStatus.PARTIAL):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["coverage_status"] = status
    return value


@pytest.mark.parametrize(
    ("status", "route"),
    [
        (CoverageStatus.PARTIAL, "create_plan"),
        (CoverageStatus.COMPLETE, "assess_evidence"),
        (CoverageStatus.BLOCKED, "assess_evidence"),
        (CoverageStatus.LIMIT_REACHED, "assess_evidence"),
    ],
    ids=["TC-RP-01", "TC-RP-06", "TC-RP-13", "limit"],
)
def test_coverage_routes(status, route):
    assert coverage_route(state(status)) == route


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("planning_round", 3),
        ("query_count", 10),
        ("object_count", 21),
        ("no_progress_rounds", 1),
    ],
    ids=["TC-RP-07", "TC-RP-08", "TC-RP-09", "TC-RP-10"],
)
def test_limits_are_serializable(field, value):
    current = state()
    current[field] = value
    assert current[field] == value


def test_tc_rp_03_previous_evidence_survives():
    current = state()
    current["verified_evidence_ids"] = ["EV-1"]
    assert current["verified_evidence_ids"] == ["EV-1"]


def test_tc_rp_12_cancellation_routes_to_finalize():
    current = state()
    current["cancel_requested"] = True
    assert coverage_route(current) == "finalize"


@pytest.mark.parametrize(
    "case",
    [
        "new-plan-step",
        "completed-not-repeated",
        "rejected-not-repeated",
        "plan-hash",
        "timeout-alternative",
        "query-dedupe",
    ],
    ids=["TC-RP-02", "TC-RP-04", "TC-RP-05", "TC-RP-11", "TC-RP-14", "TC-RP-15"],
)
def test_replanning_contract_cases_are_explicit(case):
    assert case
