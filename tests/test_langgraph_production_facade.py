from __future__ import annotations

import json

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
from legacydb_copilot.workflow.langgraph.enums import CandidateStatus
from legacydb_copilot.workflow.langgraph.graph import build_reasoning_reporting_graph
from legacydb_copilot.workflow.langgraph.production_facade import (
    ProductionInvestigationServiceFacade,
    bind_production_investigation,
    configure_production_langgraph,
    reset_production_langgraph_for_tests,
)
from legacydb_copilot.workflow.langgraph.state import create_initial_investigation_state


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


def test_production_callback_runs_at_execution_stage_not_initialize() -> None:
    facade = ProductionInvestigationServiceFacade()
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="safe investigation"
    )
    calls: list[str] = []

    with facade.bind(
        lambda: calls.append("executed")
        or ("answer", [], 0.8, None, {"investigation_id": "INV-STAGED"})
    ):
        initialized = facade.initialize(state)
        assert calls == []
        state.update(initialized)
        facade.execute_sql(state)
        assert calls == ["executed"]


def test_production_graph_reexecutes_after_contradicted_candidate() -> None:
    facade = ProductionInvestigationServiceFacade()
    calls: list[frozenset[str]] = []

    def execute(rejected: frozenset[str]):
        calls.append(rejected)
        selected = "SecondObject" if "FirstObject" in rejected else "FirstObject"
        reproduced = selected == "SecondObject"
        trace = {
            "ranked_objects": [
                {"object_type": "TABLE", "name": "FirstObject", "score": 9, "reason": "lexical"},
                {"object_type": "TABLE", "name": "SecondObject", "score": 2, "reason": "metadata"},
            ],
            "evidence_gate": {
                "reproduced": reproduced,
                "business_key_exists": reproduced,
            },
        }
        return (
            "answer",
            [],
            0.8,
            None,
            {
                "investigation_id": "INV-RECOVERY",
                "selected_primary_object": selected,
                "evidence_gate_reason": "supported" if reproduced else "not supported",
                "ai_debug_trace": json.dumps(trace),
            },
        )

    with facade.bind(execute):
        final = build_reasoning_reporting_graph(facade.handlers()).invoke(
            create_initial_investigation_state(
                investigation_id="i", workspace_id="w", question="safe investigation"
            )
        )

    assert calls == [frozenset(), frozenset({"FirstObject"})]
    statuses = {item.object_name: item.status for item in final["ranked_candidates"]}
    assert statuses["FirstObject"] is CandidateStatus.REJECTED
    assert statuses["SecondObject"] is CandidateStatus.SUPPORTED
    assert final["backtrack_count"] == 1


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
