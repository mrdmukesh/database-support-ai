from __future__ import annotations

import pytest

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.activation import (
    CallableOrchestrator,
    InvestigationOrchestratorRouter,
    LangGraphUnavailableError,
    OrchestrationContext,
    OrchestrationFailure,
    OrchestrationMode,
    OrchestrationResult,
    RouterTelemetry,
)


def context() -> OrchestrationContext:
    return OrchestrationContext("production", "workspace", "user", correlation_id="correlation")


def result() -> OrchestrationResult:
    return OrchestrationResult(payload={"answer": "graph"}, source="langgraph")


@pytest.mark.parametrize("configured_mode", ["LEGACY", "SHADOW", "COMPARE", "DISABLED", "invalid"])
def test_router_always_calls_langgraph(configured_mode):
    calls = []

    def run(selected_context):
        calls.append(selected_context)
        return result()

    router = InvestigationOrchestratorRouter(
        settings=Settings(
            environment=Environment.TESTING, investigation_orchestrator_mode=configured_mode
        ),
        langgraph=CallableOrchestrator(run),
    )
    routed = router.run(context())
    assert len(calls) == 1
    assert calls[0].selected_mode is OrchestrationMode.LANGGRAPH
    assert routed.source == "langgraph"
    assert routed.execution_metadata["workflow_engine"] == "LangGraph"
    assert routed.execution_metadata["execution_mode"] == "LANGGRAPH"
    assert routed.execution_metadata["graph_execution_id"] == "correlation"
    assert routed.execution_metadata["fallback_used"] is False


def test_unavailable_langgraph_is_reported_without_fallback():
    telemetry = RouterTelemetry()
    router = InvestigationOrchestratorRouter(
        settings=Settings(environment=Environment.TESTING), langgraph=None, telemetry=telemetry
    )
    with pytest.raises(LangGraphUnavailableError, match="unavailable"):
        router.run(context())
    assert telemetry.events[-1]["event"] == "failed"


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("graph failed"), OrchestrationFailure("timeout", stage="timeout")],
)
def test_langgraph_failure_is_logged_and_propagated_without_fallback(failure, caplog):
    def fail(_):
        raise failure

    telemetry = RouterTelemetry()
    router = InvestigationOrchestratorRouter(
        settings=Settings(environment=Environment.TESTING),
        langgraph=CallableOrchestrator(fail),
        telemetry=telemetry,
    )
    with pytest.raises(type(failure), match=str(failure)):
        router.run(context())
    assert "LangGraph execution failed" in caplog.text
    assert telemetry.events[-1]["event"] == "failed"
