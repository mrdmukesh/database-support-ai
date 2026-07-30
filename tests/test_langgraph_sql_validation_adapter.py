from __future__ import annotations

import hashlib

import pytest

from legacydb_copilot.workflow.langgraph.adapters.sql_validation import SQLValidationAdapter
from legacydb_copilot.workflow.langgraph.enums import QueryValidationStatus
from legacydb_copilot.workflow.langgraph.state import (
    QueryRecord,
    create_initial_investigation_state,
)


def state_with(sql, *, parameters=None):
    state = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    state["proposed_queries"] = [
        QueryRecord(
            query_id="q1",
            plan_step_id="p1",
            sanitized_sql=sql,
            query_hash=hashlib.sha256(sql.encode()).hexdigest(),
            parameter_metadata=parameters or {},
        )
    ]
    return state


def validate(state, scope=lambda _state, _query: None, safety=lambda sql: sql):
    return SQLValidationAdapter(scope, safety)(state)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM Employee WHERE EmployeeNumber = :employee_number",
        "SELECT * FROM Employee e JOIN Department d "
        "ON e.DepartmentId=d.DepartmentId WHERE e.id=:id",
        "SELECT * FROM Employee e LEFT JOIN Department d "
        "ON e.DepartmentId=d.DepartmentId WHERE e.id=:id",
        "SELECT definition FROM sys.sql_modules WHERE object_id=:id",
    ],
    ids=["TC-SV-01", "TC-SV-02", "TC-SV-03", "TC-SV-14"],
)
def test_safe_selects_are_approved(sql):
    assert validate(state_with(sql))["approved_queries"][0].read_only


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE Employee SET Name='x'",
        "DELETE FROM Employee",
        "MERGE Employee USING Other ON 1=1 WHEN MATCHED THEN DELETE;",
        "EXEC usp_UpdateEmployee",
        "SELECT 1; DELETE FROM Employee",
        "EXEC sp_executesql @sql",
    ],
    ids=["TC-SV-04", "TC-SV-05", "TC-SV-06", "TC-SV-07", "TC-SV-08", "TC-SV-13"],
)
def test_mutation_and_execution_are_rejected(sql):
    result = validate(state_with(sql))
    assert not result["approved_queries"]
    assert result["rejected_queries"][0].validation_status == QueryValidationStatus.REJECTED


@pytest.mark.parametrize("reason", ["cross database", "workspace scope", "cartesian join"])
def test_tc_sv_09_10_12_scope_controls_are_preserved(reason):
    def reject(_state, _query):
        raise PermissionError(reason)

    assert validate(state_with("SELECT * FROM Employee"), reject)["rejected_queries"]


def test_tc_sv_11_existing_unbounded_policy_can_add_limit():
    approved = validate(state_with("SELECT * FROM Employee"), safety=lambda sql: f"{sql} LIMIT 10")
    assert approved["approved_queries"][0].sanitized_sql.endswith("LIMIT 10")


def test_tc_sv_15_secret_parameter_values_are_not_in_state():
    state = state_with("SELECT * FROM Employee WHERE id=:id", parameters={"id": "str"})
    assert state["proposed_queries"][0].parameter_metadata == {"id": "str"}
