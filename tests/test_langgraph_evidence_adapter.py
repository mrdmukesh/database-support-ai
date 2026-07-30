from __future__ import annotations

import pytest

from legacydb_copilot.workflow.langgraph.adapters.evidence import EvidencePreservationAdapter
from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.enums import (
    EvidenceOutcome,
    QueryExecutionStatus,
)
from legacydb_copilot.workflow.langgraph.state import (
    InvestigationPlanStep,
    QueryRecord,
    create_initial_investigation_state,
    deserialize_investigation_state,
    serialize_investigation_state,
)


def state(status=QueryExecutionStatus.SUCCEEDED, rows=({"value": 1},), objects=("Employee",)):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["investigation_plan"] = [
        InvestigationPlanStep(
            step_id="p1",
            objective="DOB",
            evidence_sought="DateOfBirth",
            query_intent="ENTITY_LOOKUP",
        )
    ]
    value["query_results"] = [
        QueryRecord(
            query_id="q1",
            plan_step_id="p1",
            execution_status=status,
            result_summary=tuple(rows),
            row_count=len(rows),
            referenced_objects=objects,
        )
    ]
    return value


def preserve(value, persist=lambda _state, _result, _findings: "EV-1"):
    return EvidencePreservationAdapter(persist)(value)


def test_tc_ev_01_success_persisted():
    assert preserve(state())["query_results"][0].evidence_id == "EV-1"


def test_tc_ev_02_evidence_id_added_once():
    value = state()
    value["evidence_ids"] = ["EV-1"]
    assert preserve(value)["evidence_ids"] == ["EV-1"]


def test_tc_ev_03_duplicate_durable_result_suppressed():
    value = state()
    value["query_results"][0] = value["query_results"][0].model_copy(update={"evidence_id": "EV-1"})
    assert preserve(value)["evidence_ids"] == []


def test_tc_ev_04_verified_evidence_not_downgraded():
    value = state()
    value["verified_evidence_ids"] = ["OLD"]
    assert preserve(value)["verified_evidence_ids"] == ["OLD", "EV-1"]


def test_tc_ev_05_empty_result_is_durable():
    output = preserve(state(QueryExecutionStatus.SUCCEEDED_EMPTY, ()))
    assert output["evidence_ids"] == ["EV-1"]


def test_tc_ev_06_no_matching_row_classification():
    output = preserve(state(QueryExecutionStatus.SUCCEEDED_EMPTY, ()))
    assert output["findings"][0].finding_type == EvidenceOutcome.NO_MATCHING_ROW


def test_tc_ev_07_required_null():
    output = preserve(state(QueryExecutionStatus.SUCCEEDED_WITH_NULLS, ({"DateOfBirth": None},)))
    assert EvidenceOutcome.REQUIRED_VALUE_MISSING in {
        item.finding_type for item in output["findings"]
    }


def test_tc_ev_08_optional_null():
    output = preserve(state(QueryExecutionStatus.SUCCEEDED_WITH_NULLS, ({"MiddleName": None},)))
    assert output["findings"][0].finding_type == EvidenceOutcome.OPTIONAL_VALUE_NULL


def test_tc_ev_09_calculation_not_possible():
    output = preserve(state(QueryExecutionStatus.SUCCEEDED_WITH_NULLS, ({"DateOfBirth": None},)))
    assert EvidenceOutcome.CALCULATION_NOT_POSSIBLE in {
        item.finding_type for item in output["findings"]
    }


def test_tc_ev_10_missing_relationship():
    output = preserve(
        state(
            QueryExecutionStatus.SUCCEEDED_WITH_NULLS,
            ({"DepartmentName": None},),
            ("Employee", "Department"),
        )
    )
    assert EvidenceOutcome.RELATIONSHIP_NOT_PRESENT in {
        item.finding_type for item in output["findings"]
    }


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (QueryExecutionStatus.TIMED_OUT, "query_timed_out"),
        (QueryExecutionStatus.PERMISSION_DENIED, "permission_blocked"),
    ],
    ids=["TC-EV-11", "TC-EV-12"],
)
def test_failures_become_gaps(status, kind):
    assert preserve(state(status, ()))["evidence_gaps"][0].gap_type == kind


def test_tc_ev_13_persistence_failure_blocks_verification():
    with pytest.raises(OperationalNodeError) as error:
        preserve(state(), lambda *_args: (_ for _ in ()).throw(OSError("down")))
    assert error.value.code == "EVIDENCE_PERSISTENCE_FAILED"


def test_tc_ev_14_round_one_evidence_survives():
    value = state()
    value["evidence_ids"] = value["verified_evidence_ids"] = ["OLD"]
    assert preserve(value)["verified_evidence_ids"] == ["OLD", "EV-1"]


def test_tc_ev_15_references_survive_json_round_trip():
    value = state()
    update = preserve(value)
    value.update(update)
    restored = deserialize_investigation_state(serialize_investigation_state(value))
    assert restored["verified_evidence_ids"] == ["EV-1"]
