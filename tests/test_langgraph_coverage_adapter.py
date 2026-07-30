from __future__ import annotations

from datetime import UTC, datetime

import pytest

from legacydb_copilot.workflow.langgraph.adapters.coverage import CoverageAdapter
from legacydb_copilot.workflow.langgraph.enums import CoverageStatus, ObjectDisposition
from legacydb_copilot.workflow.langgraph.state import (
    DatabaseObjectRef,
    EvidenceGapRecord,
    create_initial_investigation_state,
)


def state(required=("a", "b", "c"), successful=()):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["required_objects"] = [
        DatabaseObjectRef(
            object_name=name, object_type="TABLE", disposition=ObjectDisposition.REQUIRED
        )
        for name in required
    ]
    value["successful_objects"] = list(successful)
    return value


def gap(kind="blocked"):
    return EvidenceGapRecord(
        gap_type=kind,
        description=kind,
        blocking=True,
        source_node="test",
        timestamp=datetime.now(UTC),
    )


def test_tc_cv_01_zero_required_objects_is_not_started():
    assert CoverageAdapter()(state(()))["coverage_status"] == CoverageStatus.NOT_STARTED


def test_tc_cv_02_one_of_three_is_partial():
    output = CoverageAdapter()(state(successful=("a",)))
    assert output["coverage_status"] == CoverageStatus.PARTIAL
    assert output["coverage_percentage"] == pytest.approx(100 / 3)


def test_tc_cv_03_all_required_complete():
    assert (
        CoverageAdapter()(state(successful=("a", "b", "c")))["coverage_status"]
        == CoverageStatus.COMPLETE
    )


def test_tc_cv_04_optional_excluded():
    value = state(("a",), ("a",))
    value["optional_objects"] = [DatabaseObjectRef(object_name="z", object_type="TABLE")]
    assert CoverageAdapter()(value)["coverage_percentage"] == 100


def test_tc_cv_05_inaccessible_required_is_blocked():
    value = state(("a",))
    value["inaccessible_objects"] = ["a"]
    assert CoverageAdapter()(value)["coverage_status"] == CoverageStatus.BLOCKED


@pytest.mark.parametrize(
    "kind",
    ["query_timed_out", "dynamic_sql", "metadata_incomplete"],
    ids=["TC-CV-06", "TC-CV-10", "metadata-gap"],
)
def test_blocking_gap_prevents_complete(kind):
    value = state(("a",), ("a",))
    value["evidence_gaps"] = [gap(kind)]
    assert CoverageAdapter()(value)["coverage_status"] != CoverageStatus.COMPLETE


@pytest.mark.parametrize(
    "classification",
    ["verified_null", "no_matching_row", "missing_relationship"],
    ids=["TC-CV-07", "TC-CV-08", "TC-CV-09"],
)
def test_conclusive_evidence_satisfies_object_coverage(classification):
    value = state(("a",), ("a",))
    value["warnings"].append(classification)
    assert CoverageAdapter()(value)["coverage_status"] == CoverageStatus.COMPLETE
