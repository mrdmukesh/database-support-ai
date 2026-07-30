from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.activation import (
    OrchestrationContext,
    OrchestrationResult,
)
from legacydb_copilot.workflow.langgraph.composition import (
    ProductionDependencies,
    build_production_langgraph_orchestrator,
    register_production_langgraph_orchestrator,
)
from legacydb_copilot.workflow.langgraph.contracts import (
    NullTelemetryRecorder,
    OperationalNodeError,
    ReasoningReportingWorkflowHandlers,
)
from legacydb_copilot.workflow.langgraph.enums import (
    CoverageStatus,
    WorkflowReasoningMode,
    WorkflowTerminalStatus,
)
from legacydb_copilot.workflow.langgraph.state import InvestigationState

ProductionRequest = Callable[[], Any]


@dataclass
class _BoundRequest:
    callback: ProductionRequest
    result: OrchestrationResult | None = None


class ProductionInvestigationServiceFacade:
    """Request-scoped bridge to the existing production investigation service pipeline.

    The existing pipeline remains the sole owner of authorization, SQL safety/execution,
    persistence, evidence, provider audit, cancellation, and report generation. The graph invokes
    that facade exactly once and never creates a second copy of those services.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    @contextmanager
    def bind(self, callback: ProductionRequest) -> Iterator[None]:
        if getattr(self._local, "request", None) is not None:
            raise RuntimeError("A production investigation request is already bound")
        self._local.request = _BoundRequest(callback)
        try:
            yield
        finally:
            self._local.request = None

    def authorize(self, _context: OrchestrationContext) -> None:
        if self._request() is None:
            raise PermissionError("Production request authorization context is unavailable")

    def initialize(self, _state: InvestigationState) -> dict[str, Any]:
        request = self._required_request()
        if request.result is not None:
            raise OperationalNodeError(
                "DUPLICATE_PRODUCTION_EXECUTION",
                "The production investigation facade was already invoked.",
            )
        payload = request.callback()
        investigation_id = ""
        if isinstance(payload, tuple) and len(payload) >= 5 and isinstance(payload[4], dict):
            investigation_id = str(payload[4].get("investigation_id") or "")
        request.result = OrchestrationResult(
            payload=payload,
            investigation_id=investigation_id,
            source="langgraph",
        )
        return {}

    @staticmethod
    def no_update(_state: InvestigationState) -> dict[str, Any]:
        return {}

    @staticmethod
    def coverage(_state: InvestigationState) -> dict[str, Any]:
        return {
            "coverage_status": CoverageStatus.COMPLETE,
            "coverage_percentage": 100.0,
            "missing_required_objects": [],
        }

    @staticmethod
    def assessment(_state: InvestigationState) -> dict[str, Any]:
        # The bound production facade has already applied the real Evidence Gate and optional
        # provider reasoning. Never issue a second provider call from the migration wrapper.
        return {
            "reasoning_allowed": False,
            "reasoning_mode": WorkflowReasoningMode.SKIP,
            "provider_call_required": False,
            "llm_skip_reason": "production_facade_already_completed_reasoning",
        }

    @staticmethod
    def report(_state: InvestigationState) -> dict[str, Any]:
        return {"structured_report": {"source": "production_investigation_service_facade"}}

    @staticmethod
    def validate_report(_state: InvestigationState) -> dict[str, Any]:
        return {"report_validation_errors": []}

    @staticmethod
    def finalize(_state: InvestigationState) -> dict[str, Any]:
        return {"terminal_status": WorkflowTerminalStatus.COMPLETED}

    def response(self, _state: InvestigationState) -> OrchestrationResult:
        request = self._required_request()
        if request.result is None:
            raise OperationalNodeError(
                "PRODUCTION_FACADE_RESULT_MISSING",
                "The production investigation facade returned no result.",
            )
        return request.result

    def handlers(self) -> ReasoningReportingWorkflowHandlers:
        return ReasoningReportingWorkflowHandlers(
            initialize=self.initialize,
            resolve_entity=self.no_update,
            discover_objects=self.no_update,
            create_plan=self.no_update,
            validate_sql=self.no_update,
            execute_sql=self.no_update,
            preserve_evidence=self.no_update,
            classify_results=self.no_update,
            check_coverage=self.coverage,
            assess_evidence=self.assessment,
            apply_evidence_gate=self.no_update,
            invoke_reasoning=self.no_update,
            validate_reasoning=self.no_update,
            compose_report=self.report,
            validate_report=self.validate_report,
            finalize=self.finalize,
        )

    def _request(self) -> _BoundRequest | None:
        return getattr(self._local, "request", None)

    def _required_request(self) -> _BoundRequest:
        request = self._request()
        if request is None:
            raise OperationalNodeError(
                "PRODUCTION_REQUEST_CONTEXT_MISSING",
                "Production request context is unavailable.",
            )
        return request


_facade = ProductionInvestigationServiceFacade()
_composition_lock = threading.Lock()
_configured = False


def configure_production_langgraph(settings: Settings | None = None) -> None:
    global _configured
    with _composition_lock:
        if _configured:
            return
        resolved = settings or Settings.from_env()
        orchestrator = build_production_langgraph_orchestrator(
            ProductionDependencies(
                handlers=_facade.handlers(),
                authorize=_facade.authorize,
                telemetry=NullTelemetryRecorder(),
                response_mapper=_facade.response,
            ),
            settings=resolved,
        )
        register_production_langgraph_orchestrator(orchestrator)
        _configured = True


@contextmanager
def bind_production_investigation(callback: ProductionRequest) -> Iterator[None]:
    with _facade.bind(callback):
        yield


def reset_production_langgraph_for_tests() -> None:
    global _configured
    with _composition_lock:
        register_production_langgraph_orchestrator(None)
        _configured = False
