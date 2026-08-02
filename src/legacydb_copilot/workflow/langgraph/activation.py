from __future__ import annotations

import hashlib
import logging
import math
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from legacydb_copilot.config import Settings
from legacydb_copilot.services.pii_masking_service import sanitize_ai_trace

logger = logging.getLogger(__name__)


class OrchestrationMode(StrEnum):
    LEGACY = "LEGACY"
    LANGGRAPH = "LANGGRAPH"
    SHADOW = "SHADOW"
    COMPARE = "COMPARE"
    DISABLED = "DISABLED"

    @classmethod
    def safe_parse(cls, value: object) -> OrchestrationMode:
        # LangGraph is the sole execution engine. Retain this parser for API
        # compatibility, but never allow configuration to select another mode.
        return cls.LANGGRAPH


class ComparisonCategory(StrEnum):
    MATCH = "MATCH"
    EQUIVALENT = "EQUIVALENT"
    LANGGRAPH_BETTER = "LANGGRAPH_BETTER"
    LEGACY_BETTER = "LEGACY_BETTER"
    MISMATCH = "MISMATCH"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    BLOCKED = "BLOCKED"


class ReleaseDecision(StrEnum):
    READY = "READY"
    READY_WITH_CONDITIONS = "READY_WITH_CONDITIONS"
    NOT_READY = "NOT_READY"
    BLOCKED_BY_ENVIRONMENT = "BLOCKED_BY_ENVIRONMENT"


@dataclass(frozen=True)
class OrchestrationContext:
    environment: str
    workspace_id: str
    user_id: str
    question: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    selected_mode: OrchestrationMode = OrchestrationMode.LANGGRAPH
    reasoning_enabled: bool = True


@dataclass(frozen=True)
class OrchestrationResult:
    payload: Any
    investigation_id: str = ""
    source: str = ""
    metrics: Mapping[str, Any] = field(default_factory=dict)
    durable_evidence_created: bool = False
    provider_invoked: bool = False
    failure_stage: str = ""
    execution_metadata: Mapping[str, Any] = field(default_factory=dict)


class InvestigationOrchestrator(Protocol):
    def run(self, context: OrchestrationContext) -> OrchestrationResult: ...


class ComparisonStore(Protocol):
    def persist(self, result: ComparisonResult) -> None: ...


@dataclass(frozen=True)
class ComparisonResult:
    comparison_id: str
    correlation_id: str
    category: ComparisonCategory
    total_score: float
    scorecard: Mapping[str, float]
    differences: Mapping[str, Any]
    release_blocking_findings: tuple[str, ...]
    selected_result: str


@dataclass(frozen=True)
class RoutingDecision:
    mode: OrchestrationMode
    cohort: int | None
    rollout_key_hash: str
    reason: str
    kill_switch_active: bool


def stable_rollout_bucket(workspace_id: str, user_id: str) -> tuple[int | None, str]:
    key = f"{workspace_id.strip()}\x1f{user_id.strip()}"
    if not workspace_id.strip() or not user_id.strip():
        return None, ""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100, digest


def select_orchestration_mode(
    settings: Settings,
    context: OrchestrationContext,
) -> RoutingDecision:
    del settings
    return RoutingDecision(OrchestrationMode.LANGGRAPH, None, "", "langgraph_only", False)


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def compare_results(
    legacy: OrchestrationResult,
    langgraph: OrchestrationResult,
    *,
    correlation_id: str,
    selected_result: str,
) -> ComparisonResult:
    left = dict(legacy.metrics)
    right = dict(langgraph.metrics)
    blockers: list[str] = []
    if left.get("authorization_ok", True) != right.get("authorization_ok", True):
        blockers.append("authorization_mismatch")
    if left.get("null_semantics") != right.get("null_semantics") and (
        left.get("null_semantics") or right.get("null_semantics")
    ):
        blockers.append("null_no_row_mismatch")
    for key in ("mutation_executed", "stored_procedure_executed", "unverified_evidence_to_llm"):
        if right.get(key):
            blockers.append(key)
    safety = 0.0 if blockers else 30.0
    legacy_verified = int(left.get("verified_evidence_count", 0))
    graph_verified = int(right.get("verified_evidence_count", 0))
    evidence = 25.0 if graph_verified >= legacy_verified else 12.5
    legacy_coverage = float(left.get("coverage", 0.0))
    graph_coverage = float(right.get("coverage", 0.0))
    coverage = 15.0 if graph_coverage >= legacy_coverage else 7.5
    unsupported = int(right.get("unsupported_claim_count", 0))
    claims = 10.0 if unsupported == 0 else 0.0
    terminal = 10.0 if left.get("terminal_status") == right.get("terminal_status") else 5.0
    latency = (
        5.0
        if float(right.get("latency_ms", math.inf)) <= float(left.get("latency_ms", math.inf))
        else 2.5
    )
    cost = 5.0 if float(right.get("cost", 0.0)) <= float(left.get("cost", 0.0)) else 2.5
    scorecard = {
        "safety": safety,
        "evidence_correctness": evidence,
        "coverage": coverage,
        "claim_support": claims,
        "terminal_behavior": terminal,
        "latency": latency,
        "cost": cost,
    }
    left_text = _normalized_text(left.get("answer", legacy.payload))
    right_text = _normalized_text(right.get("answer", langgraph.payload))
    if blockers:
        category = ComparisonCategory.BLOCKED
    elif not left_text or not right_text:
        category = ComparisonCategory.NOT_COMPARABLE
    elif left == right or (left_text == right_text and legacy_verified == graph_verified):
        category = ComparisonCategory.MATCH
    elif graph_verified > legacy_verified or graph_coverage > legacy_coverage:
        category = ComparisonCategory.LANGGRAPH_BETTER
    elif graph_verified < legacy_verified or graph_coverage < legacy_coverage:
        category = ComparisonCategory.LEGACY_BETTER
    elif set(left_text.split()) == set(right_text.split()):
        category = ComparisonCategory.EQUIVALENT
    else:
        category = ComparisonCategory.MISMATCH
    differences = sanitize_ai_trace(
        {
            "evidence_count": graph_verified - legacy_verified,
            "coverage": graph_coverage - legacy_coverage,
            "query_count": int(right.get("query_count", 0)) - int(left.get("query_count", 0)),
            "llm_invoked": [
                bool(left.get("llm_invoked")),
                bool(right.get("llm_invoked")),
            ],
            "tokens": int(right.get("tokens", 0)) - int(left.get("tokens", 0)),
            "cost": float(right.get("cost", 0.0)) - float(left.get("cost", 0.0)),
            "latency_ms": float(right.get("latency_ms", 0.0)) - float(left.get("latency_ms", 0.0)),
            "terminal_status": [
                left.get("terminal_status", ""),
                right.get("terminal_status", ""),
            ],
        }
    )
    return ComparisonResult(
        comparison_id=str(uuid.uuid4()),
        correlation_id=correlation_id,
        category=category,
        total_score=sum(scorecard.values()),
        scorecard=scorecard,
        differences=differences,
        release_blocking_findings=tuple(blockers),
        selected_result=selected_result,
    )


class DisabledInvestigationError(RuntimeError):
    pass


class LangGraphUnavailableError(RuntimeError):
    pass


class OrchestrationFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        durable_evidence_created: bool = False,
        provider_invoked: bool = False,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.durable_evidence_created = durable_evidence_created
        self.provider_invoked = provider_invoked


@dataclass
class CallableOrchestrator:
    callback: Callable[[OrchestrationContext], OrchestrationResult]

    def run(self, context: OrchestrationContext) -> OrchestrationResult:
        return self.callback(context)


@dataclass
class RouterTelemetry:
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event: Mapping[str, Any]) -> None:
        self.events.append(dict(sanitize_ai_trace(dict(event))))


class InvestigationOrchestratorRouter:
    def __init__(
        self,
        *,
        settings: Settings,
        langgraph: InvestigationOrchestrator | None,
        telemetry: RouterTelemetry | None = None,
    ) -> None:
        self.settings = settings
        self.langgraph = langgraph
        self.telemetry = telemetry or RouterTelemetry()

    def run(self, context: OrchestrationContext) -> OrchestrationResult:
        decision = select_orchestration_mode(self.settings, context)
        started_at = datetime.now(UTC)
        base_event = {
            "correlation_id": context.correlation_id,
            "mode": decision.mode.value,
            "reason": decision.reason,
            "rollout_cohort": decision.cohort,
            "rollout_key_hash": decision.rollout_key_hash,
            "kill_switch_active": decision.kill_switch_active,
            "execution_started_at": started_at.isoformat(),
        }
        self.telemetry.record({**base_event, "event": "selected"})
        if self.langgraph is None:
            error = LangGraphUnavailableError("LangGraph workflow is unavailable.")
            logger.error("LangGraph workflow unavailable", extra=base_event)
            self.telemetry.record({**base_event, "event": "failed", "failure_stage": "unavailable"})
            raise error
        try:
            result = self.langgraph.run(replace(context, selected_mode=OrchestrationMode.LANGGRAPH))
            return self._with_execution_metadata(result, context, decision, started_at=started_at)
        except Exception as exc:
            failure_stage = (
                exc.stage if isinstance(exc, OrchestrationFailure) else type(exc).__name__
            )
            logger.exception(
                "LangGraph execution failed", extra={**base_event, "failure_stage": failure_stage}
            )
            self.telemetry.record({**base_event, "event": "failed", "failure_stage": failure_stage})
            raise

    def _with_execution_metadata(
        self,
        result: OrchestrationResult,
        context: OrchestrationContext,
        decision: RoutingDecision,
        *,
        started_at: datetime,
    ) -> OrchestrationResult:
        metadata = {
            "workflow_engine": "LangGraph",
            "execution_mode": OrchestrationMode.LANGGRAPH.value,
            "graph_version": "langgraph-v1",
            "graph_execution_id": context.correlation_id,
            "requested_model": self.settings.llm_requested_model
            or self.settings.llm_reasoning_model,
            "effective_model": self.settings.selected_reasoning_model,
            "provider": self.settings.llm_provider,
            "reasoning_effort": self.settings.llm_reasoning_effort,
            "selected_by": "Admin" if decision.reason == "explicit_mode" else "Automatic",
            "fallback_used": False,
            "fallback_reason": "",
            "execution_started_at": started_at,
            "execution_ended_at": datetime.now(UTC),
            "selection_reason": decision.reason,
        }
        return replace(result, execution_metadata=metadata)


@dataclass(frozen=True)
class ReleaseGateInput:
    environment_available: bool = True
    mutation_executed: bool = False
    stored_procedure_executed: bool = False
    authorization_violation: bool = False
    unverified_evidence_to_llm: bool = False
    fabricated_invocation: bool = False
    secret_leakage: bool = False
    unsupported_proof_of_fix: bool = False
    regressions_passed: bool = False
    defaults_safe: bool = True
    kill_switch_passed: bool = True
    benchmark_passed: bool = False


def evaluate_release_gates(gates: ReleaseGateInput) -> tuple[ReleaseDecision, tuple[str, ...]]:
    if not gates.environment_available:
        return ReleaseDecision.BLOCKED_BY_ENVIRONMENT, ("live_environment_unavailable",)
    critical = tuple(
        name
        for name in (
            "mutation_executed",
            "stored_procedure_executed",
            "authorization_violation",
            "unverified_evidence_to_llm",
            "fabricated_invocation",
            "secret_leakage",
            "unsupported_proof_of_fix",
        )
        if getattr(gates, name)
    )
    controls_failed = (
        not gates.regressions_passed or not gates.defaults_safe or not gates.kill_switch_passed
    )
    if critical or controls_failed:
        return ReleaseDecision.NOT_READY, critical or ("regression_or_control_gate_failed",)
    if not gates.benchmark_passed:
        return ReleaseDecision.READY_WITH_CONDITIONS, ("protected_benchmark_required",)
    return ReleaseDecision.READY, ()
