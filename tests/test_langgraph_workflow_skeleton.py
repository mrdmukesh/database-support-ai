import asyncio
import copy
import importlib
import inspect
import sys
from collections.abc import Callable

import pytest

from legacydb_copilot.routers import chat
from legacydb_copilot.workflow.langgraph.contracts import (
    InMemoryTelemetryRecorder,
    InvestigationWorkflowHandlers,
    OperationalNodeError,
)
from legacydb_copilot.workflow.langgraph.enums import (
    EntityResolutionStatus,
    EvidenceOutcome,
    ObjectDisposition,
    QueryExecutionStatus,
    QueryValidationStatus,
    RelationshipVerification,
    WorkflowReasoningMode,
    WorkflowTerminalStatus,
)
from legacydb_copilot.workflow.langgraph.graph import (
    EDGE_SEQUENCE,
    NODE_ORDER,
    build_investigation_graph,
)
from legacydb_copilot.workflow.langgraph.state import (
    DatabaseObjectRef,
    FindingRecord,
    InvestigationPlanStep,
    QueryRecord,
    RelationshipEdge,
    ResolvedEntityRecord,
    create_initial_investigation_state,
)


def initial_state(investigation_id: str = "INV-1"):
    return create_initial_investigation_state(
        investigation_id=investigation_id,
        workspace_id="WS-1",
        correlation_id=f"CORR-{investigation_id}",
        question="Why is employee E-1 incomplete?",
    )


def employee_object(**overrides):
    values = {
        "database": "Payroll",
        "schema_name": "dbo",
        "object_name": "Employee",
        "object_type": "TABLE",
        "disposition": ObjectDisposition.REQUIRED,
    }
    values.update(overrides)
    return DatabaseObjectRef(**values)


def make_handlers(
    execution_log: list[str],
    overrides: dict[str, Callable] | None = None,
) -> InvestigationWorkflowHandlers:
    def initialize(state):
        execution_log.append("initialize")
        return {"warnings": [*state["warnings"], "initialized"]}

    def resolve_entity(state):
        execution_log.append("resolve_entity")
        assert "initialized" in state["warnings"]
        entity = ResolvedEntityRecord(
            entity_type="employee",
            business_key="EmployeeId",
            matched_value="E-1",
            database="Payroll",
            schema_name="dbo",
            table="Employee",
            column="EmployeeId",
            matching_method="exact",
            deterministic_rank=1,
            evidence_id="ENTITY-1",
        )
        return {
            "entity_resolution_status": EntityResolutionStatus.RESOLVED,
            "resolved_entities": [entity],
        }

    def discover_objects(state):
        execution_log.append("discover_objects")
        assert state["entity_resolution_status"] is EntityResolutionStatus.RESOLVED
        item = employee_object()
        return {"candidate_objects": [item], "required_objects": [item], "object_count": 1}

    def create_plan(state):
        execution_log.append("create_plan")
        assert state["required_objects"]
        step = InvestigationPlanStep(
            step_id="PLAN-1",
            objective="Inspect employee",
            database="Payroll",
            object_name="Employee",
            object_type="TABLE",
            evidence_sought="Employee row",
            query_intent="READ_ONLY_LOOKUP",
            required_objects=("Payroll.dbo.Employee",),
        )
        return {"investigation_plan": [step], "planning_round": 1}

    def validate_sql(state):
        execution_log.append("validate_sql")
        assert state["investigation_plan"][0].step_id == "PLAN-1"
        query = QueryRecord(
            query_id="QUERY-1",
            plan_step_id="PLAN-1",
            sanitized_sql="SELECT EmployeeId FROM dbo.Employee WHERE EmployeeId = :employee_id",
            parameter_metadata={"employee_id": "str"},
            validation_status=QueryValidationStatus.APPROVED,
        )
        return {"approved_queries": [query]}

    def execute_sql(state):
        execution_log.append("execute_sql")
        query = state["approved_queries"][0].model_copy(
            update={
                "execution_status": QueryExecutionStatus.SUCCEEDED,
                "row_count": 1,
                "evidence_id": "SQL-1",
            }
        )
        return {"query_results": [query], "query_count": 1}

    def preserve_evidence(state):
        execution_log.append("preserve_evidence")
        assert state["query_results"][0].evidence_id == "SQL-1"
        return {"evidence_ids": ["SQL-1"], "verified_evidence_ids": ["SQL-1"]}

    def assess_evidence(state):
        execution_log.append("assess_evidence")
        assert state["verified_evidence_ids"] == ["SQL-1"]
        return {
            "reasoning_allowed": True,
            "reasoning_mode": WorkflowReasoningMode.NORMAL_ROOT_CAUSE,
        }

    def compose_report(state):
        execution_log.append("compose_report")
        assert state["reasoning_allowed"]
        return {"structured_report": {"report_id": "REPORT-1", "evidence_ids": ["SQL-1"]}}

    def finalize(state):
        execution_log.append("finalize")
        assert state["structured_report"]
        return {"terminal_status": WorkflowTerminalStatus.COMPLETED}

    values = {
        "initialize": initialize,
        "resolve_entity": resolve_entity,
        "discover_objects": discover_objects,
        "create_plan": create_plan,
        "validate_sql": validate_sql,
        "execute_sql": execute_sql,
        "preserve_evidence": preserve_evidence,
        "assess_evidence": assess_evidence,
        "compose_report": compose_report,
        "finalize": finalize,
    }
    values.update(overrides or {})
    return InvestigationWorkflowHandlers(**values)


def test_graph_compiles() -> None:
    graph = build_investigation_graph(make_handlers([]))
    assert graph is not None


def test_expected_nodes_exist() -> None:
    graph = build_investigation_graph(make_handlers([]))
    registered = set(graph.get_graph().nodes)
    assert set(NODE_ORDER) <= registered
    assert len(set(NODE_ORDER)) == 10


def test_expected_linear_order() -> None:
    log: list[str] = []
    build_investigation_graph(make_handlers(log)).invoke(initial_state())
    assert log == list(NODE_ORDER)


def test_minimal_investigation_completes() -> None:
    result = build_investigation_graph(make_handlers([])).invoke(initial_state())
    assert result["terminal_status"] is WorkflowTerminalStatus.COMPLETED


def test_investigation_identity_survives() -> None:
    state = initial_state()
    result = build_investigation_graph(make_handlers([])).invoke(state)
    for field_name in ("investigation_id", "workspace_id", "correlation_id", "question"):
        assert result[field_name] == state[field_name]


def test_state_survives_across_nodes() -> None:
    result = build_investigation_graph(make_handlers([])).invoke(initial_state())
    assert result["resolved_entities"][0].matched_value == "E-1"
    assert result["required_objects"][0].object_name == "Employee"
    assert result["investigation_plan"][0].step_id == "PLAN-1"
    assert result["query_results"][0].row_count == 1
    assert result["structured_report"]["report_id"] == "REPORT-1"


def test_evidence_survives_downstream_nodes() -> None:
    result = build_investigation_graph(make_handlers([])).invoke(initial_state())
    assert result["evidence_ids"] == result["verified_evidence_ids"] == ["SQL-1"]
    assert result["structured_report"]["evidence_ids"] == ["SQL-1"]


def test_no_external_dependencies_or_credentials_are_required(monkeypatch) -> None:
    for name in ("OPENAI_API_KEY", "AZURE_CLIENT_SECRET", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    result = build_investigation_graph(make_handlers([])).invoke(initial_state())
    assert result["terminal_status"] is WorkflowTerminalStatus.COMPLETED


def test_nodes_cannot_corrupt_callers_mutable_input() -> None:
    state = initial_state()
    original = copy.deepcopy(state)

    def attempted_mutation(node_state):
        node_state["warnings"].append("hidden mutation")
        return {"warnings": ["initialized"]}

    handlers = make_handlers([], {"initialize": attempted_mutation})
    build_investigation_graph(handlers).invoke(state)
    assert state == original


def test_current_and_previous_node_tracking() -> None:
    result = build_investigation_graph(make_handlers([])).invoke(initial_state())
    assert result["previous_node"] == "compose_report"
    assert result["current_node"] == "finalize"


def test_node_telemetry_order() -> None:
    telemetry = InMemoryTelemetryRecorder()
    build_investigation_graph(make_handlers([]), telemetry=telemetry).invoke(initial_state())
    observed = [(event.node_name, event.event_type) for event in telemetry.events]
    expected = [(name, event) for name in NODE_ORDER for event in ("started", "finished")]
    assert observed == expected


def test_node_durations_are_non_negative() -> None:
    telemetry = InMemoryTelemetryRecorder()
    build_investigation_graph(make_handlers([]), telemetry=telemetry).invoke(initial_state())
    finished = [event for event in telemetry.events if event.event_type == "finished"]
    assert finished
    assert all(event.duration_ms is not None and event.duration_ms >= 0 for event in finished)


def test_expected_operational_failure_is_sanitized_and_halts_handlers() -> None:
    log: list[str] = []

    def denied(_state):
        log.append("discover_objects")
        raise OperationalNodeError(
            "METADATA_PERMISSION_DENIED",
            "Metadata access denied; Password=Secret123",
            context={"password": "Secret123"},
        )

    result = build_investigation_graph(
        make_handlers(log, {"discover_objects": denied})
    ).invoke(initial_state())
    assert log == ["initialize", "resolve_entity", "discover_objects"]
    assert result["terminal_status"] is WorkflowTerminalStatus.FAILED
    assert result["resolved_entities"]
    assert "Secret123" not in result["errors"][0].model_dump_json()
    assert not result["approved_queries"]


def test_unexpected_exception_is_telemetry_recorded_and_reraised() -> None:
    telemetry = InMemoryTelemetryRecorder()

    def defect(_state):
        raise RuntimeError("unexpected defect")

    graph = build_investigation_graph(
        make_handlers([], {"create_plan": defect}),
        telemetry=telemetry,
    )
    with pytest.raises(RuntimeError, match="unexpected defect"):
        graph.invoke(initial_state())
    event = telemetry.events[-1]
    assert event.node_name == "create_plan"
    assert event.success is False
    assert event.error_code == "RuntimeError"


def test_operational_failure_masks_secrets_in_state_and_telemetry() -> None:
    telemetry = InMemoryTelemetryRecorder()

    def denied(_state):
        raise OperationalNodeError("DENIED", "Password=Secret123")

    result = build_investigation_graph(
        make_handlers([], {"resolve_entity": denied}),
        telemetry=telemetry,
    ).invoke(initial_state())
    assert "Secret123" not in result["stop_reason"]
    assert "Secret123" not in result["errors"][0].message
    assert all("Secret123" not in event.error_code for event in telemetry.events)


def test_empty_evidence_path_can_complete_without_verified_evidence() -> None:
    def preserve(_state):
        return {"evidence_ids": [], "verified_evidence_ids": []}

    def assess(state):
        assert not state["evidence_ids"]
        return {
            "reasoning_allowed": False,
            "reasoning_mode": WorkflowReasoningMode.NO_VERIFIED_EVIDENCE,
            "llm_skip_reason": "No verified evidence.",
        }

    def report(state):
        assert state["reasoning_mode"] is WorkflowReasoningMode.NO_VERIFIED_EVIDENCE
        return {"structured_report": {"report_id": "REPORT-NO-EVIDENCE"}}

    result = build_investigation_graph(
        make_handlers(
            [],
            {
                "preserve_evidence": preserve,
                "assess_evidence": assess,
                "compose_report": report,
            },
        )
    ).invoke(initial_state())
    assert result["terminal_status"] is WorkflowTerminalStatus.COMPLETED
    assert result["reasoning_mode"] is WorkflowReasoningMode.NO_VERIFIED_EVIDENCE


def test_null_finding_survives_graph() -> None:
    def preserve(_state):
        finding = FindingRecord(
            finding_type=EvidenceOutcome.REQUIRED_VALUE_MISSING,
            object_name="Employee",
            column_name="DateOfBirth",
            description="DateOfBirth = NULL",
            blocking=True,
        )
        return {
            "evidence_ids": ["SQL-1"],
            "verified_evidence_ids": ["SQL-1"],
            "findings": [finding],
        }

    result = build_investigation_graph(
        make_handlers([], {"preserve_evidence": preserve})
    ).invoke(initial_state())
    assert result["findings"][0].finding_type is EvidenceOutcome.REQUIRED_VALUE_MISSING


def test_entity_relationship_survives_graph() -> None:
    edge = RelationshipEdge(
        source_object="Employee",
        source_column="DepartmentId",
        target_object="Department",
        target_column="DepartmentId",
        relationship_type="FOREIGN_KEY",
        verification=RelationshipVerification.VERIFIED,
        source="schema_metadata",
    )

    def discover(_state):
        return {
            "candidate_objects": [employee_object()],
            "required_objects": [employee_object()],
            "relationship_edges": [edge],
            "object_count": 1,
        }

    result = build_investigation_graph(
        make_handlers([], {"discover_objects": discover})
    ).invoke(initial_state())
    assert result["relationship_edges"] == [edge]


def test_join_plan_survives_graph() -> None:
    step = InvestigationPlanStep(
        step_id="JOIN-1",
        objective="Join employee and department",
        evidence_sought="Department name",
        query_intent="READ_ONLY_JOIN",
        required_objects=("dbo.Employee", "dbo.Department"),
        join_justification="Verified DepartmentId foreign key",
        relationship_source="META-1",
    )

    def plan(_state):
        return {"investigation_plan": [step], "planning_round": 1}

    def validate(state):
        assert state["investigation_plan"][0] == step
        query = QueryRecord(
            query_id="JOIN-Q",
            plan_step_id="JOIN-1",
            validation_status=QueryValidationStatus.APPROVED,
        )
        return {"approved_queries": [query]}

    result = build_investigation_graph(
        make_handlers([], {"create_plan": plan, "validate_sql": validate})
    ).invoke(initial_state())
    restored = result["investigation_plan"][0]
    assert restored.join_justification == "Verified DepartmentId foreign key"
    assert restored.required_objects == ("dbo.Employee", "dbo.Department")


def test_stored_procedure_metadata_survives_graph() -> None:
    procedure = employee_object(
        object_name="usp_CalculateEmployeeAge",
        object_type="STORED_PROCEDURE",
        inspection_only=True,
        contains_mutation=False,
    )

    def discover(_state):
        return {
            "candidate_objects": [procedure],
            "required_objects": [employee_object()],
            "object_count": 2,
        }

    result = build_investigation_graph(
        make_handlers([], {"discover_objects": discover})
    ).invoke(initial_state())
    assert result["candidate_objects"][0] == procedure


def test_mutating_procedure_remains_inspection_only() -> None:
    procedure = employee_object(
        object_name="usp_UpdateEmployee",
        object_type="STORED_PROCEDURE",
        inspection_only=True,
        contains_mutation=True,
    )

    def discover(_state):
        return {
            "candidate_objects": [procedure],
            "required_objects": [employee_object()],
            "object_count": 2,
        }

    result = build_investigation_graph(
        make_handlers([], {"discover_objects": discover})
    ).invoke(initial_state())
    item = result["candidate_objects"][0]
    assert item.inspection_only and item.contains_mutation
    assert all(query.plan_step_id != item.object_name for query in result["approved_queries"])


def test_compiled_graph_is_reusable_without_state_leakage() -> None:
    graph = build_investigation_graph(make_handlers([]))
    first = graph.invoke(initial_state("INV-A"))
    second = graph.invoke(initial_state("INV-B"))
    assert first["investigation_id"] == "INV-A"
    assert second["investigation_id"] == "INV-B"
    assert first["correlation_id"] != second["correlation_id"]


def test_async_execution_matches_synchronous_execution() -> None:
    graph = build_investigation_graph(make_handlers([]))
    synchronous = graph.invoke(initial_state("SYNC"))
    asynchronous = asyncio.run(graph.ainvoke(initial_state("ASYNC")))
    for field_name in (
        "terminal_status",
        "current_node",
        "previous_node",
        "evidence_ids",
        "reasoning_mode",
    ):
        assert asynchronous[field_name] == synchronous[field_name]


def test_graph_module_import_has_no_execution_side_effects() -> None:
    sys.modules.pop("legacydb_copilot.workflow.langgraph.graph", None)
    module = importlib.import_module("legacydb_copilot.workflow.langgraph.graph")
    assert callable(module.build_investigation_graph)
    assert not any(name.startswith("compiled_graph") for name in vars(module))


def test_production_chat_route_still_uses_existing_orchestration() -> None:
    source = inspect.getsource(chat.ask_chat_question)
    assert "_run_dynamic_investigation(" in source
    assert "build_investigation_graph" not in source
    assert chat.ask_chat_question.__module__ == "legacydb_copilot.routers.chat"


def test_edge_sequence_is_exactly_linear() -> None:
    assert tuple(
        zip(
            ("__start__", *NODE_ORDER),
            (*NODE_ORDER, "__end__"),
            strict=True,
        )
    ) == EDGE_SEQUENCE
