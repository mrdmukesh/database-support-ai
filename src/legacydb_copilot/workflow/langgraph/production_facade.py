from __future__ import annotations

import inspect
import json
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
from legacydb_copilot.workflow.langgraph.adapters.candidates import (
    CandidateEvaluationAdapter,
    CandidateExpansionAdapter,
    CandidateRejectionAdapter,
    CandidateSelectionAdapter,
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
    CandidateStatus,
    CoverageStatus,
    EvidenceOutcome,
    WorkflowReasoningMode,
    WorkflowTerminalStatus,
)
from legacydb_copilot.workflow.langgraph.state import (
    CandidateObjectRecord,
    FindingRecord,
    InvestigationState,
)

ProductionRequest = Callable[..., Any]


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

    def initialize(self, state: InvestigationState) -> dict[str, Any]:
        return {
            "graph_step_count": state["graph_step_count"] + 1,
            "candidate_transition_trace": [
                *state["candidate_transition_trace"],
                {
                    "node": "initialize",
                    "decision": "question_understood",
                    "reason": "Authorized production request entered staged LangGraph execution.",
                },
            ],
        }

    def execute_sql(self, state: InvestigationState) -> dict[str, Any]:
        """Invoke the existing safe production service at the execution boundary exactly once."""
        request = self._required_request()
        rejected = frozenset(
            item.qualified_name
            for item in state["ranked_candidates"]
            if item.status is CandidateStatus.REJECTED
        )
        parameters = inspect.signature(request.callback).parameters
        payload = request.callback(rejected) if parameters else request.callback()
        investigation_id = ""
        if isinstance(payload, tuple) and len(payload) >= 5 and isinstance(payload[4], dict):
            investigation_id = str(payload[4].get("investigation_id") or "")
        request.result = OrchestrationResult(
            payload=payload,
            investigation_id=investigation_id,
            source="langgraph",
        )
        return {
            "graph_step_count": state["graph_step_count"] + 1,
            "candidate_transition_trace": [
                *state["candidate_transition_trace"],
                {
                    "node": "execute_sql",
                    "decision": "production_evidence_pipeline_executed",
                    "reason": (
                        "Existing authorization, read-only SQL, evidence, and persistence "
                        "services completed."
                    ),
                },
            ],
        }

    def classify_results(self, state: InvestigationState) -> dict[str, Any]:
        request = self._required_request()
        if request.result is None:
            return {"stop_reason": "Production evidence result is unavailable."}
        payload = request.result.payload
        metadata = payload[4] if isinstance(payload, tuple) and len(payload) >= 5 else {}
        raw_trace = metadata.get("ai_debug_trace", "{}") if isinstance(metadata, dict) else "{}"
        try:
            trace = json.loads(raw_trace) if isinstance(raw_trace, str) else dict(raw_trace)
        except (TypeError, ValueError):
            trace = {}
        ranked = trace.get("ranked_objects") or []
        selected = str(metadata.get("selected_primary_object") or "")
        candidates: list[CandidateObjectRecord] = []
        prior = {item.qualified_name.casefold(): item for item in state["ranked_candidates"]}
        for rank, raw in enumerate(ranked[: state["max_candidate_tables"]], start=1):
            name = str(raw.get("name") or "")
            if not name:
                continue
            schema, _, leaf = name.rpartition(".")
            previous = prior.get(name.casefold())
            candidates.append(
                previous
                or CandidateObjectRecord(
                    candidate_id=f"{raw.get('object_type', 'TABLE')}:{name}".casefold(),
                    object_type=str(raw.get("object_type") or "TABLE"),
                    object_name=leaf or name,
                    schema_name=schema,
                    rank=rank,
                    score=float(raw.get("score") or 0.0),
                    lexical_relevance=float(raw.get("score") or 0.0),
                    reasons=(str(raw.get("reason") or "Production metadata candidate."),),
                    attempt_count=1 if name.casefold() == selected.casefold() else 0,
                )
            )
        for previous in state["ranked_candidates"]:
            if previous.qualified_name.casefold() not in {
                item.qualified_name.casefold() for item in candidates
            }:
                candidates.append(previous)
        active = next(
            (item for item in candidates if item.qualified_name.casefold() == selected.casefold()),
            None,
        )
        gate = trace.get("evidence_gate") or {}
        reproduced = bool(gate.get("reproduced"))
        business_key_exists = bool(gate.get("business_key_exists"))
        findings = list(state["findings"])
        if active is not None:
            outcome = (
                EvidenceOutcome.VALUE_PRESENT
                if reproduced
                else EvidenceOutcome.NO_MATCHING_ROW
                if not business_key_exists
                else EvidenceOutcome.METADATA_INCOMPLETE
            )
            findings.append(
                FindingRecord(
                    finding_type=outcome,
                    object_name=active.qualified_name,
                    description=(
                        "Production evidence reproduced the reported condition."
                        if reproduced
                        else "Production evidence did not support the selected candidate."
                    ),
                )
            )
        return {
            "ranked_candidates": candidates,
            "active_candidate_id": active.candidate_id if active else "",
            "findings": findings,
            "graph_step_count": state["graph_step_count"] + 1,
            "candidate_transition_trace": [
                *state["candidate_transition_trace"],
                {
                    "node": "classify_results",
                    "candidate_id": active.candidate_id if active else "",
                    "decision": "reproduced" if reproduced else "not_reproduced",
                    "reason": str(metadata.get("evidence_gate_reason") or "Evidence classified."),
                },
            ],
        }

    @staticmethod
    def stage(node: str):
        def handler(state: InvestigationState) -> dict[str, Any]:
            return {
                "graph_step_count": state["graph_step_count"] + 1,
                "candidate_transition_trace": [
                    *state["candidate_transition_trace"],
                    {
                        "node": node,
                        "decision": "completed",
                        "reason": f"Production LangGraph completed {node} stage.",
                    },
                ],
            }

        return handler

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
        result = request.result
        payload = result.payload
        if isinstance(payload, tuple) and len(payload) >= 5 and isinstance(payload[4], dict):
            parts = list(payload)
            metadata = dict(parts[4])
            raw_trace = metadata.get("ai_debug_trace", "{}")
            try:
                trace = json.loads(raw_trace) if isinstance(raw_trace, str) else dict(raw_trace)
            except (TypeError, ValueError):
                trace = {}
            trace["candidate_transition_trace"] = list(
                _state.get("candidate_transition_trace") or []
            )
            trace["backtrack_count"] = int(_state.get("backtrack_count") or 0)
            trace["expansion_count"] = int(_state.get("expansion_count") or 0)
            trace["workflow_ranked_candidates"] = [
                {
                    "candidate_id": item.candidate_id,
                    "qualified_name": item.qualified_name,
                    "rank": item.rank,
                    "score": item.score,
                    "status": item.status.value,
                    "attempt_count": item.attempt_count,
                    "reasons": list(item.reasons),
                }
                for item in (_state.get("ranked_candidates") or [])
            ]
            metadata["ai_debug_trace"] = json.dumps(trace, default=str)
            parts[4] = metadata
            result = OrchestrationResult(
                payload=tuple(parts),
                investigation_id=result.investigation_id,
                source=result.source,
                metrics=result.metrics,
                durable_evidence_created=result.durable_evidence_created,
                provider_invoked=result.provider_invoked,
                failure_stage=result.failure_stage,
                execution_metadata=result.execution_metadata,
            )
            request.result = result
        return result

    def handlers(self) -> ReasoningReportingWorkflowHandlers:
        return ReasoningReportingWorkflowHandlers(
            initialize=self.initialize,
            resolve_entity=self.stage("resolve_entity"),
            discover_objects=self.stage("discover_objects"),
            select_candidate=CandidateSelectionAdapter(),
            create_plan=self.stage("create_plan"),
            validate_sql=self.stage("validate_sql"),
            execute_sql=self.execute_sql,
            preserve_evidence=self.stage("preserve_evidence"),
            classify_results=self.classify_results,
            evaluate_candidate=CandidateEvaluationAdapter(),
            reject_candidate=CandidateRejectionAdapter(),
            expand_discovery=CandidateExpansionAdapter(),
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
