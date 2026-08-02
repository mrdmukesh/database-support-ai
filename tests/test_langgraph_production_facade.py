from __future__ import annotations

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.activation import (
    OrchestrationContext,
    OrchestrationMode,
    select_orchestration_mode,
)
from legacydb_copilot.workflow.langgraph.composition import (
    get_production_langgraph_orchestrator,
)
from legacydb_copilot.workflow.langgraph.production_facade import (
    bind_production_investigation,
    configure_production_langgraph,
    reset_production_langgraph_for_tests,
)


def test_registered_composition_invokes_bound_production_facade_once():
    reset_production_langgraph_for_tests()
    configure_production_langgraph(Settings(environment=Environment.TESTING))
    orchestrator = get_production_langgraph_orchestrator()
    calls = []

    with bind_production_investigation(
        lambda: calls.append("called")
        or ("answer", [], 0.8, None, {"investigation_id": "INV-1"})
    ):
        result = orchestrator.run(
            OrchestrationContext(
                "test", "workspace", "user", "safe investigation", "correlation"
            )
        )

    assert calls == ["called"]
    assert result.source == "langgraph"
    assert result.investigation_id == "INV-1"
    reset_production_langgraph_for_tests()


def test_registration_activates_langgraph_despite_retired_flags():
    reset_production_langgraph_for_tests()
    settings = Settings(
        environment=Environment.TESTING,
        langgraph_enabled=False,
        investigation_orchestrator_mode="LEGACY",
    )
    configure_production_langgraph(settings)

    decision = select_orchestration_mode(
        settings, OrchestrationContext("test", "workspace", "user")
    )

    assert get_production_langgraph_orchestrator() is not None
    assert decision.mode is OrchestrationMode.LANGGRAPH
    reset_production_langgraph_for_tests()


def test_evaluation_environment_can_be_explicitly_authorized():
    settings = Settings(
        environment=Environment.TESTING,
        langgraph_enabled=True,
        investigation_orchestrator_mode="LANGGRAPH",
        llm_model_access_verified=True,
    )
    decision = select_orchestration_mode(
        settings, OrchestrationContext("evaluation", "workspace", "user")
    )
    assert decision.mode is OrchestrationMode.LANGGRAPH


def test_missing_composition_does_not_select_legacy():
    reset_production_langgraph_for_tests()
    settings = Settings(
        environment=Environment.TESTING,
        langgraph_enabled=False,
        investigation_orchestrator_mode="LANGGRAPH",
    )

    decision = select_orchestration_mode(
        settings, OrchestrationContext("test", "workspace", "user")
    )

    assert get_production_langgraph_orchestrator() is None
    assert decision.mode is OrchestrationMode.LANGGRAPH
