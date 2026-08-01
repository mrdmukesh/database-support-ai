from __future__ import annotations

import pytest

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.workflow.langgraph.adapters.coverage import (
    CoverageAdapter,
    DeterministicAssessmentAdapter,
)
from legacydb_copilot.workflow.langgraph.adapters.evidence import EvidencePreservationAdapter
from legacydb_copilot.workflow.langgraph.adapters.planning import PlanningAdapter
from legacydb_copilot.workflow.langgraph.adapters.sql_execution import SQLExecutionAdapter
from legacydb_copilot.workflow.langgraph.adapters.sql_validation import SQLValidationAdapter
from legacydb_copilot.workflow.langgraph.contracts import EvidenceDrivenWorkflowHandlers
from legacydb_copilot.workflow.langgraph.enums import (
    EntityResolutionStatus,
    ObjectDisposition,
    WorkflowTerminalStatus,
)
from legacydb_copilot.workflow.langgraph.graph import build_evidence_driven_graph
from legacydb_copilot.workflow.langgraph.state import (
    DatabaseObjectRef,
    ResolvedEntityRecord,
    create_initial_investigation_state,
)


def initial():
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="Investigate employee EMP-1002"
    )
    state["entity_resolution_status"] = EntityResolutionStatus.RESOLVED
    state["resolved_entities"] = [
        ResolvedEntityRecord(
            entity_type="employee",
            business_key="EmployeeNumber",
            matched_value="EMP-1002",
            table="Employee",
            column="EmployeeNumber",
            matching_method="exact",
        )
    ]
    employee = DatabaseObjectRef(
        object_name="Employee", object_type="TABLE", disposition=ObjectDisposition.REQUIRED
    )
    state["selected_objects"] = state["required_objects"] = [employee]
    state["object_count"] = 1
    return state


def compiled(evidence, persist=lambda _state, result, _findings: f"EV-{result.query_id}"):
    def noop(_state):
        return {}

    planning = PlanningAdapter(
        lambda step, _state: [
            PlannedQuery(
                "DOB lookup",
                f"SELECT DateOfBirth FROM {step.object_name} WHERE EmployeeNumber=:id",
                query_id=f"Q-{step.planning_round}",
            )
        ]
    )
    handlers = EvidenceDrivenWorkflowHandlers(
        initialize=noop,
        resolve_entity=noop,
        discover_objects=noop,
        create_plan=planning,
        validate_sql=SQLValidationAdapter(lambda _state, _query: None, lambda sql: sql),
        execute_sql=SQLExecutionAdapter(lambda _queries: [evidence], lambda _state: None),
        preserve_evidence=EvidencePreservationAdapter(persist),
        classify_results=noop,
        check_coverage=CoverageAdapter(),
        assess_evidence=DeterministicAssessmentAdapter(),
        compose_report=lambda state: {
            "structured_report": {
                "deterministic": True,
                "evidence_ids": list(state["verified_evidence_ids"]),
            }
        },
        finalize=lambda _state: {"terminal_status": WorkflowTerminalStatus.COMPLETED},
    )
    return build_evidence_driven_graph(handlers)


@pytest.mark.parametrize(
    ("case", "evidence"),
    [
        ("valid-dob", EvidenceResult("p", "SELECT", [{"DateOfBirth": "1990-05-01"}])),
        ("null-dob", EvidenceResult("p", "SELECT", [{"DateOfBirth": None}])),
        ("employee-not-found", EvidenceResult("p", "SELECT", [])),
        ("missing-department", EvidenceResult("p", "SELECT", [{"DepartmentName": None}])),
        ("valid-join", EvidenceResult("p", "SELECT", [{"DepartmentName": "Finance"}])),
        ("mutating-procedure-metadata", EvidenceResult("p", "SELECT", [{"definition": "UPDATE"}])),
        ("dynamic-sql-metadata", EvidenceResult("p", "SELECT", [{"dynamic_sql": True}])),
        ("timeout", EvidenceResult("p", "SELECT", [], execution_status="timed_out")),
        ("permission", EvidenceResult("p", "SELECT", [], execution_status="permission_denied")),
        ("multi-hop", EvidenceResult("p", "SELECT", [{"TaxCode": "T1"}])),
        ("no-progress", EvidenceResult("p", "SELECT", [], execution_status="failed")),
    ],
    ids=[f"Scenario-{number}" for number in range(1, 12)],
)
def test_isolated_evidence_scenarios_terminate_without_llm(case, evidence):
    result = compiled(evidence).invoke(initial())
    assert result["terminal_status"] == WorkflowTerminalStatus.COMPLETED
    assert result["provider_call_required"] is False
    assert case


def test_scenario_10_persistence_failure_blocks_reasoning():
    graph = compiled(
        EvidenceResult("p", "SELECT", [{"DateOfBirth": "1990-05-01"}]),
        persist=lambda *_args: (_ for _ in ()).throw(OSError("storage down")),
    )
    result = graph.invoke(initial())
    assert result["terminal_status"] == WorkflowTerminalStatus.FAILED
    assert result["verified_evidence_ids"] == []
