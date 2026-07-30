from __future__ import annotations

import pytest

from legacydb_copilot.workflow.langgraph.adapters.reporting import ReportValidationAdapter
from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.state import create_initial_investigation_state


def state(report=None):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["structured_report"] = report
    value["verified_evidence_ids"] = ["EV-1"]
    return value


def test_valid_report_persisted():
    output = ReportValidationAdapter(lambda _r, _s: [], lambda _s, _r: ["ART-1"])(
        state({"evidence_ids": ["EV-1"]})
    )
    assert output["report_artifact_ids"] == ["ART-1"]


@pytest.mark.parametrize(
    "error",
    [
        "schema invalid",
        "unknown evidence ID",
        "unsupported root cause",
        "unsupported recommendation",
        "proof of fix unsupported",
        "NULL/no-row conflict",
        "secret leakage",
        "terminal status mismatch",
    ],
)
def test_invalid_reports_require_review(error):
    output = ReportValidationAdapter(lambda _r, _s: [error], lambda _s, _r: ["BAD"])(
        state({"summary": "x"})
    )
    assert output["quality_review_required"]
    assert output["report_artifact_ids"] == []


def test_missing_report_requires_review():
    assert ReportValidationAdapter(lambda _r, _s: [], lambda _s, _r: [])(state())[
        "quality_review_required"
    ]


def test_report_persistence_failure_is_operational():
    adapter = ReportValidationAdapter(
        lambda _r, _s: [],
        lambda _s, _r: (_ for _ in ()).throw(OSError("down")),
    )
    with pytest.raises(OperationalNodeError) as error:
        adapter(state({"summary": "safe"}))
    assert error.value.code == "REPORT_PERSISTENCE_FAILED"
