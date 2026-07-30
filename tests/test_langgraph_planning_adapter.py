from __future__ import annotations

import pytest

from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.workflow.langgraph.adapters.planning import PlanningAdapter
from legacydb_copilot.workflow.langgraph.enums import (
    EntityResolutionStatus,
    ObjectDisposition,
)
from legacydb_copilot.workflow.langgraph.state import (
    DatabaseObjectRef,
    RelationshipEdge,
    ResolvedEntityRecord,
    create_initial_investigation_state,
)


def workflow_state():
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="Investigate EMP-1001"
    )
    state["entity_resolution_status"] = EntityResolutionStatus.RESOLVED
    state["resolved_entities"] = [
        ResolvedEntityRecord(
            entity_type="employee",
            business_key="EmployeeNumber",
            matched_value="EMP-1001",
            table="Employee",
            column="EmployeeNumber",
            matching_method="exact",
        )
    ]
    required = DatabaseObjectRef(
        object_name="Employee", object_type="TABLE", disposition=ObjectDisposition.REQUIRED
    )
    optional = DatabaseObjectRef(
        object_name="Department", object_type="TABLE", disposition=ObjectDisposition.OPTIONAL
    )
    state["selected_objects"] = [required, optional]
    state["required_objects"] = [required]
    state["optional_objects"] = [optional]
    return state


def generator(step, _state):
    return [PlannedQuery(step.object_name, f"SELECT * FROM {step.object_name} WHERE id = :id")]


def test_tc_pl_01_basic_employee_plan():
    update = PlanningAdapter(generator)(workflow_state())
    assert update["investigation_plan"][0].object_name == "Employee"


def test_tc_pl_02_required_object_before_optional():
    update = PlanningAdapter(generator)(workflow_state())
    assert [step.required for step in update["investigation_plan"]] == [True, False]


def test_tc_pl_03_join_justification_preserved():
    state = workflow_state()
    state["relationship_edges"] = [
        RelationshipEdge(
            source_object="Employee",
            source_column="DepartmentId",
            target_object="Department",
            target_column="DepartmentId",
            relationship_type="foreign_key",
            verification="VERIFIED",
            source="metadata",
        )
    ]
    assert (
        "DepartmentId"
        in PlanningAdapter(generator)(state)["investigation_plan"][0].join_justification
    )


@pytest.mark.parametrize(
    ("mutation", "dynamic"),
    [(False, False), (True, False), (False, True)],
    ids=["TC-PL-04-inspection", "TC-PL-05-mutation", "TC-PL-06-dynamic"],
)
def test_procedure_is_metadata_only(mutation, dynamic):
    state = workflow_state()
    procedure = DatabaseObjectRef(
        object_name="usp_Age",
        object_type="PROCEDURE",
        disposition=ObjectDisposition.REQUIRED,
        inspection_only=True,
        contains_mutation=mutation,
        contains_dynamic_sql=dynamic,
        unsafe_to_execute=mutation or dynamic,
    )
    state["selected_objects"] = state["required_objects"] = [procedure]
    step = PlanningAdapter(generator)(state)["investigation_plan"][0]
    assert step.inspection_only and step.query_intent == "PROCEDURE_DEFINITION"


def test_tc_pl_07_completed_step_not_repeated():
    state = workflow_state()
    state["successful_objects"] = ["Employee"]
    update = PlanningAdapter(generator)(state)
    assert all(step.object_name != "Employee" for step in update["investigation_plan"])


def test_tc_pl_08_rejected_sql_not_regenerated():
    state = workflow_state()
    first = PlanningAdapter(generator)(state)
    state["rejected_query_hashes"] = [first["proposed_queries"][0].query_hash]
    second = PlanningAdapter(generator)(state)
    assert all(
        query.query_hash not in state["rejected_query_hashes"]
        for query in second["proposed_queries"]
    )


def test_tc_pl_09_round_increments():
    state = workflow_state()
    state["planning_round"] = 1
    assert PlanningAdapter(generator)(state)["planning_round"] == 2


def test_tc_pl_10_query_budget_respected():
    state = workflow_state()
    state["max_queries"] = 1
    assert len(PlanningAdapter(generator)(state)["proposed_queries"]) == 1
