from __future__ import annotations

from legacydb_copilot.services.entity_resolution_service import (
    EntityCandidate,
    EntityResolution,
    EntityResolutionResult,
)
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.workflow.langgraph.adapters.entity_resolution import EntityResolutionAdapter
from legacydb_copilot.workflow.langgraph.adapters.relationship_discovery import (
    DiscoverySnapshot,
    RelationshipDiscoveryAdapter,
)
from legacydb_copilot.workflow.langgraph.contracts import InvestigationWorkflowHandlers
from legacydb_copilot.workflow.langgraph.enums import WorkflowTerminalStatus
from legacydb_copilot.workflow.langgraph.graph import build_investigation_graph
from legacydb_copilot.workflow.langgraph.state import create_initial_investigation_state


def state(identifier="EMP-1", suffix=""):
    return create_initial_investigation_state(
        investigation_id=f"i{suffix}",
        workspace_id="w",
        question="employee",
        requested_entity=identifier,
    )


def entity_adapter(result):
    return EntityResolutionAdapter(
        object(),
        lambda _state: MetadataSearchResult([], [], [], "v"),
        lambda _state: None,
        resolver=lambda *_args: result,
    )


def exact():
    candidate = EntityCandidate("EMP-1", {}, "E-1", "employee", "employee_code")
    return EntityResolutionResult(
        "resolved",
        [
            EntityResolution(
                "EMP-1",
                "EMP-1",
                "exact",
                1,
                "E-1",
                [candidate],
                "Exact.",
                "employee",
                "employee_code",
            )
        ],
    )


def graph(result, snapshot_provider):
    def noop(_state):
        return {}

    handlers = InvestigationWorkflowHandlers(
        initialize=noop,
        resolve_entity=entity_adapter(result),
        discover_objects=RelationshipDiscoveryAdapter(snapshot_provider, lambda _state: None),
        create_plan=noop,
        validate_sql=noop,
        execute_sql=noop,
        preserve_evidence=noop,
        assess_evidence=noop,
        compose_report=noop,
        finalize=noop,
    )
    return build_investigation_graph(handlers)


def test_tc_gr_01_exact_entity_flows_to_relationship_discovery():
    snapshot = DiscoverySnapshot(
        MetadataSearchResult(
            [TableMetadata("employee", ["employee_code"], 1, ["employee_code"], [], [])],
            [],
            [],
            "v",
        )
    )
    output = graph(exact(), lambda _state: snapshot).invoke(state())
    assert output["selected_objects"][0].object_name == "employee"


def test_tc_gr_02_ambiguous_entity_never_calls_discovery():
    calls = []
    result = EntityResolutionResult(
        "ambiguous", [EntityResolution("1", None, "ambiguous", 0, "", reason="ambiguous")]
    )
    output = graph(result, lambda value: calls.append(value)).invoke(state("1"))
    assert output["terminal_status"] == WorkflowTerminalStatus.AMBIGUOUS_ENTITY
    assert calls == []


def test_tc_gr_03_not_found_never_calls_discovery():
    calls = []
    result = EntityResolutionResult(
        "not_found", [EntityResolution("x", None, "not_found", 0, "", reason="missing")]
    )
    output = graph(result, lambda value: calls.append(value)).invoke(state("x"))
    assert output["terminal_status"] == WorkflowTerminalStatus.ENTITY_NOT_FOUND
    assert calls == []


def test_tc_gr_04_metadata_permission_failure_preserves_entity_and_sanitizes_error():
    def denied(_state):
        raise PermissionError("password=hunter2")

    output = graph(exact(), denied).invoke(state())
    assert output["resolved_entities"][0].matched_value == "EMP-1"
    assert output["terminal_status"] == WorkflowTerminalStatus.FAILED
    assert "hunter2" not in output["errors"][0].message


def test_tc_gr_05_reusable_graph_keeps_runs_isolated():
    snapshot = DiscoverySnapshot(
        MetadataSearchResult(
            [TableMetadata("employee", ["employee_code"], 1, ["employee_code"], [], [])],
            [],
            [],
            "v",
        )
    )
    compiled = graph(exact(), lambda _state: snapshot)
    first = compiled.invoke(state(suffix="1"))
    second = compiled.invoke(state(suffix="2"))
    first["warnings"].append("first")
    assert second["warnings"] == []
