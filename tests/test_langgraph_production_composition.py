from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic_core import PydanticSerializationError

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.activation import (
    LangGraphUnavailableError,
    OrchestrationContext,
    OrchestrationResult,
)
from legacydb_copilot.workflow.langgraph.composition import (
    LangGraphInvestigationOrchestrator,
    get_production_langgraph_orchestrator,
    langgraph_health,
    register_production_langgraph_orchestrator,
)
from legacydb_copilot.workflow.langgraph.state import (
    create_initial_investigation_state,
    serialize_investigation_state,
)


class Graph:
    def __init__(self):
        self.states = []

    def invoke(self, state):
        state["structured_report"] = {"answer": state["question"]}
        self.states.append(state)
        return state


def context(value="one"):
    return OrchestrationContext(
        environment="test",
        workspace_id="workspace",
        user_id="user",
        question=value,
        correlation_id=value,
    )


def settings(**updates):
    return replace(Settings(environment=Environment.TESTING), **updates)


def orchestrator(graph=None, authorize=lambda _: None, state_factory=None, **updates):
    return LangGraphInvestigationOrchestrator(
        graph=graph or Graph(),
        settings=settings(**updates),
        authorize=authorize,
        response_mapper=lambda state: OrchestrationResult(
            payload=state["structured_report"],
            investigation_id=state["investigation_id"],
            source="langgraph",
            durable_evidence_created=bool(state["evidence_ids"]),
            provider_invoked=state["ai_reasoning_invoked"],
        ),
        state_factory=state_factory,
    )


def test_orchestrator_authorizes_before_graph_invocation():
    events = []
    graph = Graph()
    runner = orchestrator(
        graph,
        authorize=lambda _: events.append("authorized"),
    )
    runner.run(context())
    assert events == ["authorized"]
    assert len(graph.states) == 1


def test_authorization_failure_prevents_graph_invocation():
    graph = Graph()
    runner = orchestrator(
        graph,
        authorize=lambda _: (_ for _ in ()).throw(PermissionError("denied")),
    )
    with pytest.raises(PermissionError):
        runner.run(context())
    assert graph.states == []


def test_reusable_graph_keeps_investigation_state_isolated():
    graph = Graph()
    runner = orchestrator(graph)
    first = runner.run(context("first"))
    second = runner.run(context("second"))
    assert first.investigation_id != second.investigation_id
    assert graph.states[0]["question"] == "first"
    assert graph.states[1]["question"] == "second"
    assert graph.states[0] is not graph.states[1]


def test_shadow_reasoning_disabled_is_explicit_without_fake_invocation():
    graph = Graph()
    runner = orchestrator(graph)
    shadow = replace(context(), reasoning_enabled=False)
    response = runner.run(shadow)
    state = graph.states[0]
    assert state["llm_skip_reason"] == "shadow_llm_disabled"
    assert state["llm_invocation_ids"] == []
    assert response.provider_invoked is False


def test_service_objects_cannot_enter_serialized_state():
    state = create_initial_investigation_state(
        investigation_id="id",
        workspace_id="workspace",
        question="question",
    )
    state["reasoning_result"] = {"service": object()}
    with pytest.raises(PydanticSerializationError):
        serialize_investigation_state(state)


def test_concurrency_is_bounded():
    runner = orchestrator(langgraph_max_concurrent_runs=1)
    assert runner._slots.acquire(blocking=False)
    try:
        with pytest.raises(LangGraphUnavailableError, match="concurrency"):
            runner.run(context())
    finally:
        runner._slots.release()


def test_registration_is_reversible():
    runner = orchestrator()
    register_production_langgraph_orchestrator(runner)
    assert get_production_langgraph_orchestrator() is runner
    register_production_langgraph_orchestrator(None)
    assert get_production_langgraph_orchestrator() is None


def test_health_is_sanitized_and_legacy_readiness_independent():
    status = langgraph_health(
        settings(
            langgraph_allowed_workspace_ids=("secret-workspace",),
            langgraph_allowed_user_ids=("secret-user",),
        ),
        production_dependencies_available=False,
        graph_compiles=False,
    )
    assert status["production_dependencies_available"] is False
    assert "secret" not in str(status)
    assert "allowed_workspace_ids" not in status


def test_graph_state_preserves_correlation_and_deadline():
    graph = Graph()
    runner = orchestrator(graph, langgraph_timeout_seconds=30)
    runner.run(context())
    state = graph.states[0]
    assert state["correlation_id"] == "one"
    assert state["deadline_at"] > state["started_at"]
