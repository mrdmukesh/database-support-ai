from __future__ import annotations

from dataclasses import replace

import pytest

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.activation import (
    CallableOrchestrator,
    DisabledInvestigationError,
    InvestigationOrchestratorRouter,
    LangGraphUnavailableError,
    OrchestrationContext,
    OrchestrationFailure,
    OrchestrationResult,
    RouterTelemetry,
)


class Store:
    def __init__(self, *, fails: bool = False):
        self.results = []
        self.fails = fails

    def persist(self, result):
        if self.fails:
            raise RuntimeError("store secret=hidden")
        self.results.append(result)


def config(mode="LEGACY", **updates):
    return replace(
        Settings(
            environment=Environment.TESTING,
            langgraph_enabled=True,
            investigation_orchestrator_mode=mode,
        ),
        **updates,
    )


def ctx():
    return OrchestrationContext(
        environment="test",
        workspace_id="workspace",
        user_id="user",
        question="question",
        correlation_id="correlation",
    )


def result(name, **metrics):
    return OrchestrationResult(
        payload={"answer": name},
        investigation_id=f"{name}-id",
        source=name,
        metrics={"answer": name, **metrics},
    )


def orchestrator(name, calls, *, failure=None):
    def run(context):
        calls.append(context)
        if failure:
            raise failure
        return result(name)

    return CallableOrchestrator(run)


def test_legacy_mode_calls_only_legacy():
    legacy_calls, graph_calls = [], []
    router = InvestigationOrchestratorRouter(
        settings=config(),
        legacy=orchestrator("legacy", legacy_calls),
        langgraph=orchestrator("langgraph", graph_calls),
    )
    assert router.run(ctx()).source == "legacy"
    assert len(legacy_calls) == 1
    assert graph_calls == []


def test_langgraph_mode_calls_only_langgraph():
    legacy_calls, graph_calls = [], []
    router = InvestigationOrchestratorRouter(
        settings=config("LANGGRAPH"),
        legacy=orchestrator("legacy", legacy_calls),
        langgraph=orchestrator("langgraph", graph_calls),
    )
    assert router.run(ctx()).source == "langgraph"
    assert legacy_calls == []
    assert len(graph_calls) == 1


@pytest.mark.parametrize("mode", ["SHADOW", "COMPARE"])
def test_dual_modes_return_exactly_one_legacy_response(mode):
    legacy_calls, graph_calls = [], []
    store = Store()
    router = InvestigationOrchestratorRouter(
        settings=config(mode),
        legacy=orchestrator("legacy", legacy_calls),
        langgraph=orchestrator("langgraph", graph_calls),
        comparison_store=store,
    )
    response = router.run(ctx())
    assert response.payload == {"answer": "legacy"}
    assert len(legacy_calls) == len(graph_calls) == 1
    assert store.results[0].correlation_id == "correlation"


def test_shadow_disables_reasoning_by_default():
    graph_contexts = []
    router = InvestigationOrchestratorRouter(
        settings=config("SHADOW", langgraph_shadow_llm_enabled=False),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=orchestrator("langgraph", graph_contexts),
    )
    router.run(ctx())
    assert graph_contexts[0].reasoning_enabled is False


def test_shadow_reasoning_can_be_explicitly_enabled():
    graph_contexts = []
    router = InvestigationOrchestratorRouter(
        settings=config("SHADOW", langgraph_shadow_llm_enabled=True),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=orchestrator("langgraph", graph_contexts),
    )
    router.run(ctx())
    assert graph_contexts[0].reasoning_enabled is True


def test_compare_candidate_response_requires_explicit_configuration():
    router = InvestigationOrchestratorRouter(
        settings=config("COMPARE", langgraph_compare_response_source="langgraph"),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=CallableOrchestrator(lambda _: result("langgraph")),
    )
    assert router.run(ctx()).source == "langgraph"


def test_shadow_failure_never_changes_legacy_response():
    router = InvestigationOrchestratorRouter(
        settings=config("SHADOW"),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=CallableOrchestrator(lambda _: (_ for _ in ()).throw(TimeoutError())),
    )
    assert router.run(ctx()).source == "legacy"


def test_comparison_persistence_failure_is_isolated_and_sanitized():
    telemetry = RouterTelemetry()
    router = InvestigationOrchestratorRouter(
        settings=config("COMPARE"),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=CallableOrchestrator(lambda _: result("langgraph")),
        comparison_store=Store(fails=True),
        telemetry=telemetry,
    )
    assert router.run(ctx()).source == "legacy"
    assert any(event["event"] == "comparison_persistence_failed" for event in telemetry.events)
    assert "hidden" not in str(telemetry.events)


def test_disabled_mode_invokes_neither_workflow():
    calls = []
    router = InvestigationOrchestratorRouter(
        settings=config("DISABLED"),
        legacy=orchestrator("legacy", calls),
        langgraph=orchestrator("langgraph", calls),
    )
    with pytest.raises(DisabledInvestigationError):
        router.run(ctx())
    assert calls == []


def test_unavailable_langgraph_falls_back_with_shared_correlation():
    calls = []
    telemetry = RouterTelemetry()
    router = InvestigationOrchestratorRouter(
        settings=config("LANGGRAPH"),
        legacy=orchestrator("legacy", calls),
        langgraph=None,
        telemetry=telemetry,
    )
    assert router.run(ctx()).source == "legacy"
    assert calls[0].correlation_id == "correlation"
    assert any(event["event"] == "fallback" for event in telemetry.events)


def test_fallback_disabled_returns_safe_error_without_legacy_call():
    calls = []
    router = InvestigationOrchestratorRouter(
        settings=config("LANGGRAPH", langgraph_fallback_to_legacy=False),
        legacy=orchestrator("legacy", calls),
        langgraph=None,
    )
    with pytest.raises(LangGraphUnavailableError, match="unavailable"):
        router.run(ctx())
    assert calls == []


def test_langgraph_failure_then_legacy_failure_is_not_hidden():
    router = InvestigationOrchestratorRouter(
        settings=config("LANGGRAPH"),
        legacy=CallableOrchestrator(lambda _: (_ for _ in ()).throw(RuntimeError("legacy"))),
        langgraph=CallableOrchestrator(lambda _: (_ for _ in ()).throw(RuntimeError("graph"))),
    )
    with pytest.raises(RuntimeError, match="legacy"):
        router.run(ctx())


def test_kill_switch_prevents_shadow_dispatch():
    graph_calls = []
    router = InvestigationOrchestratorRouter(
        settings=config("SHADOW", langgraph_kill_switch=True),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=orchestrator("langgraph", graph_calls),
    )
    assert router.run(ctx()).source == "legacy"
    assert graph_calls == []


def test_pre_evidence_timeout_falls_back_when_enabled():
    router = InvestigationOrchestratorRouter(
        settings=config("LANGGRAPH", langgraph_fallback_on_timeout=True),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=CallableOrchestrator(
            lambda _: (_ for _ in ()).throw(
                OrchestrationFailure("timeout", stage="timeout")
            )
        ),
    )
    assert router.run(ctx()).source == "legacy"


def test_timeout_after_durable_evidence_does_not_duplicate_work():
    router = InvestigationOrchestratorRouter(
        settings=config("LANGGRAPH", langgraph_fallback_on_timeout=True),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=CallableOrchestrator(
            lambda _: (_ for _ in ()).throw(
                OrchestrationFailure(
                    "timeout",
                    stage="timeout",
                    durable_evidence_created=True,
                )
            )
        ),
    )
    with pytest.raises(LangGraphUnavailableError, match="human review"):
        router.run(ctx())


def test_provider_failure_does_not_silently_duplicate_provider_call():
    router = InvestigationOrchestratorRouter(
        settings=config("LANGGRAPH", langgraph_fallback_on_provider_failure=False),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=CallableOrchestrator(
            lambda _: (_ for _ in ()).throw(
                OrchestrationFailure(
                    "provider",
                    stage="provider",
                    provider_invoked=True,
                )
            )
        ),
    )
    with pytest.raises(LangGraphUnavailableError, match="human review"):
        router.run(ctx())


def test_validation_failure_fallback_is_policy_controlled():
    router = InvestigationOrchestratorRouter(
        settings=config("LANGGRAPH", langgraph_fallback_on_validation_failure=True),
        legacy=CallableOrchestrator(lambda _: result("legacy")),
        langgraph=CallableOrchestrator(
            lambda _: (_ for _ in ()).throw(
                OrchestrationFailure("invalid", stage="report_validation")
            )
        ),
    )
    assert router.run(ctx()).source == "legacy"
