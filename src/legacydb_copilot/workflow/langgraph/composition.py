from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.activation import (
    LangGraphUnavailableError,
    OrchestrationContext,
    OrchestrationResult,
)
from legacydb_copilot.workflow.langgraph.contracts import (
    ReasoningReportingWorkflowHandlers,
    TelemetryRecorder,
)
from legacydb_copilot.workflow.langgraph.graph import build_reasoning_reporting_graph
from legacydb_copilot.workflow.langgraph.state import (
    InvestigationState,
    create_initial_investigation_state,
    serialize_investigation_state,
)


class AuthorizationBoundary(Protocol):
    def __call__(self, context: OrchestrationContext) -> None: ...


class GraphInvoker(Protocol):
    def invoke(self, state: InvestigationState) -> Mapping[str, Any]: ...


StateFactory = Callable[[OrchestrationContext], InvestigationState]
ResponseMapper = Callable[[InvestigationState], OrchestrationResult]
_production_orchestrator: LangGraphInvestigationOrchestrator | None = None


@dataclass(frozen=True)
class ProductionDependencies:
    handlers: ReasoningReportingWorkflowHandlers
    authorize: AuthorizationBoundary
    telemetry: TelemetryRecorder
    response_mapper: ResponseMapper


class LangGraphInvestigationOrchestrator:
    """Authorized, bounded adapter around one reusable compiled graph."""

    def __init__(
        self,
        *,
        graph: GraphInvoker,
        settings: Settings,
        authorize: AuthorizationBoundary,
        response_mapper: ResponseMapper,
        state_factory: StateFactory | None = None,
    ) -> None:
        self._graph = graph
        self._settings = settings
        self._authorize = authorize
        self._response_mapper = response_mapper
        self._state_factory = state_factory or self._default_state
        self._slots = threading.BoundedSemaphore(settings.langgraph_max_concurrent_runs)

    def _default_state(self, context: OrchestrationContext) -> InvestigationState:
        now = datetime.now(UTC)
        state = create_initial_investigation_state(
            investigation_id=f"lg-{context.correlation_id}",
            workspace_id=context.workspace_id,
            actor_id=context.user_id,
            correlation_id=context.correlation_id,
            question=context.question,
            environment=context.environment,
            created_at=now,
            deadline_at=now + timedelta(seconds=self._settings.langgraph_timeout_seconds),
        )
        if not context.reasoning_enabled:
            state["reasoning_allowed"] = False
            state["provider_call_required"] = False
            state["llm_skip_reason"] = "shadow_llm_disabled"
            state["deterministic_fallback_reason"] = "shadow_llm_disabled"
        state["max_candidate_tables"] = self._settings.langgraph_max_candidate_tables
        state["max_candidate_columns"] = self._settings.langgraph_max_candidate_columns
        state["max_candidate_code_objects"] = (
            self._settings.langgraph_max_candidate_code_objects
        )
        state["max_backtracks"] = self._settings.langgraph_max_backtracks
        state["max_expansions"] = self._settings.langgraph_max_expansions
        state["max_graph_steps"] = self._settings.langgraph_max_graph_steps
        return state

    def run(self, context: OrchestrationContext) -> OrchestrationResult:
        self._authorize(context)
        if not self._slots.acquire(blocking=False):
            raise LangGraphUnavailableError("LangGraph concurrency limit reached.")
        try:
            initial = self._state_factory(context)
            # Validation also proves that no injected service object entered graph state.
            serialize_investigation_state(initial)
            final = dict(self._graph.invoke(initial))
            return self._response_mapper(final)  # type: ignore[arg-type]
        finally:
            self._slots.release()


def build_production_langgraph_orchestrator(
    dependencies: ProductionDependencies,
    *,
    settings: Settings,
    state_factory: StateFactory | None = None,
) -> LangGraphInvestigationOrchestrator:
    """Composition root: compile the graph using existing, request-safe service facades."""
    graph = build_reasoning_reporting_graph(
        dependencies.handlers,
        telemetry=dependencies.telemetry,
    )
    return LangGraphInvestigationOrchestrator(
        graph=graph,
        settings=settings,
        authorize=dependencies.authorize,
        response_mapper=dependencies.response_mapper,
        state_factory=state_factory,
    )


def register_production_langgraph_orchestrator(
    orchestrator: LangGraphInvestigationOrchestrator | None,
) -> None:
    """Register an application-lifetime composition; None is the safe rollback state."""
    global _production_orchestrator
    _production_orchestrator = orchestrator


def get_production_langgraph_orchestrator() -> LangGraphInvestigationOrchestrator | None:
    return _production_orchestrator


def langgraph_health(
    settings: Settings,
    *,
    production_dependencies_available: bool,
    graph_compiles: bool,
) -> dict[str, object]:
    """Sanitized operational status; allowlists and identifiers are intentionally omitted."""
    return {
        "langgraph_installed": True,
        "langgraph_graph_compiles": graph_compiles,
        "langgraph_enabled": True,
        "orchestrator_mode": "LANGGRAPH",
        "kill_switch_active": False,
        "fallback_enabled": False,
        "shadow_percentage": 0,
        "rollout_percentage": 100,
        "shadow_llm_enabled": False,
        "production_dependencies_available": production_dependencies_available,
    }
