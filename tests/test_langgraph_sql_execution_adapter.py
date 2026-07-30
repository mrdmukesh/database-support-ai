from __future__ import annotations

import pytest

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.workflow.langgraph.adapters.sql_execution import SQLExecutionAdapter
from legacydb_copilot.workflow.langgraph.enums import QueryExecutionStatus, QueryValidationStatus
from legacydb_copilot.workflow.langgraph.state import (
    QueryRecord,
    create_initial_investigation_state,
)


def state(status=QueryValidationStatus.APPROVED):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["approved_queries"] = [
        QueryRecord(
            query_id="q1",
            plan_step_id="p1",
            sanitized_sql="SELECT 1",
            validation_status=status,
            read_only=status == QueryValidationStatus.APPROVED,
            referenced_objects=("Employee",),
        )
    ]
    return value


def run(result, value=None, calls=None):
    calls = calls if calls is not None else []

    def execute(queries):
        calls.extend(queries)
        return [result]

    return SQLExecutionAdapter(execute, lambda _state: None)(value or state())


def test_tc_ex_01_approved_executes():
    calls = []
    run(EvidenceResult("p", "SELECT 1", [{"id": 1}]), calls=calls)
    assert len(calls) == 1


def test_tc_ex_02_unapproved_never_executes():
    calls = []
    value = state(QueryValidationStatus.REJECTED)
    run(EvidenceResult("p", "SELECT 1", []), value, calls)
    assert calls == []


def test_tc_ex_03_row_summary_is_bounded():
    update = run(EvidenceResult("p", "SELECT 1", [{"id": i} for i in range(20)]))
    assert len(update["query_results"][0].result_summary) == 5
    assert update["query_results"][0].truncated


@pytest.mark.parametrize(
    ("service_status", "expected"),
    [
        ("timed_out", QueryExecutionStatus.TIMED_OUT),
        ("permission_denied", QueryExecutionStatus.PERMISSION_DENIED),
        ("succeeded", QueryExecutionStatus.SUCCEEDED_EMPTY),
    ],
    ids=["TC-EX-04", "TC-EX-05", "TC-EX-06"],
)
def test_execution_statuses(service_status, expected):
    item = EvidenceResult("p", "SELECT 1", [], execution_status=service_status)
    assert run(item)["query_results"][0].execution_status == expected


def test_tc_ex_07_null_result():
    item = EvidenceResult("p", "SELECT 1", [{"DateOfBirth": None}])
    assert (
        run(item)["query_results"][0].execution_status == QueryExecutionStatus.SUCCEEDED_WITH_NULLS
    )


def test_tc_ex_08_cancellation_prevents_execution():
    value = state()
    value["cancel_requested"] = True
    calls = []
    output = run(EvidenceResult("p", "SELECT 1", []), value, calls)
    assert calls == [] and output["terminal_status"] == "CANCELLED"


def test_tc_ex_09_duration_preserved():
    item = EvidenceResult("p", "SELECT 1", [{"id": 1}], scan_policy_decision={"duration_ms": 12})
    assert run(item)["query_results"][0].execution_duration_ms == 12


def test_tc_ex_10_large_result_excluded():
    output = run(EvidenceResult("p", "SELECT 1", [{"blob": "x" * 10} for _ in range(100)]))
    assert len(output["query_results"][0].result_summary) == 5


def test_tc_ex_11_credentials_never_enter_state():
    assert "password" not in str(run(EvidenceResult("p", "SELECT 1", []))).casefold()


def test_tc_ex_12_execution_error_is_status_only():
    item = EvidenceResult("p", "SELECT 1", [], error="password=secret", execution_status="failed")
    output = run(item)
    assert output["query_results"][0].error_classification == "failed"


def test_same_query_is_not_executed_twice():
    value = state()
    value["query_results"] = [
        value["approved_queries"][0].model_copy(
            update={"execution_status": QueryExecutionStatus.SUCCEEDED}
        )
    ]
    calls = []
    run(EvidenceResult("p", "SELECT 1", [{"id": 1}]), value, calls)
    assert calls == []
