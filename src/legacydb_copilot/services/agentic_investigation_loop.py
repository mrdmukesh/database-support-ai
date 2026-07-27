from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy.orm import Session

from legacydb_copilot.db.models import (
    InvestigationAgenticStepModel,
    InvestigationModel,
)
from legacydb_copilot.services.evidence_execution_service import (
    EvidenceResult,
    execute_evidence_plan,
)
from legacydb_copilot.services.investigation_state_machine import (
    InvestigationState,
    InvestigationStateService,
)
from legacydb_copilot.services.safe_investigation_planner import (
    ActionOutcome,
    EnvironmentPolicy,
    EvidenceRequest,
    InvestigationBudget,
    PlannerStatus,
    PreviousAction,
    SafeInvestigationPlanner,
)
from legacydb_copilot.services.safe_sql_service import (
    PlannedQuery,
    plan_safe_queries,
    validate_read_only_sql,
)


@dataclass(frozen=True)
class AgenticLoopLimits:
    max_iterations: int = 8
    max_sql_queries: int = 16
    max_total_rows: int = 1000
    max_execution_seconds: float = 120.0
    max_llm_calls: int = 8
    max_tokens: int = 32000
    max_retries: int = 1

    def __post_init__(self) -> None:
        numeric = (
            self.max_iterations,
            self.max_sql_queries,
            self.max_total_rows,
            self.max_execution_seconds,
        )
        if any(value <= 0 for value in numeric):
            raise ValueError("Iteration, query, row, and duration limits must be positive")
        if min(self.max_llm_calls, self.max_tokens, self.max_retries) < 0:
            raise ValueError("LLM and retry limits cannot be negative")

    @classmethod
    def from_settings(cls, settings) -> AgenticLoopLimits:
        return cls(
            max_iterations=settings.agentic_max_iterations,
            max_sql_queries=settings.agentic_max_sql_queries,
            max_total_rows=settings.agentic_max_total_rows,
            max_execution_seconds=settings.agentic_max_execution_seconds,
            max_llm_calls=settings.agentic_max_llm_calls,
            max_tokens=settings.agentic_max_tokens,
            max_retries=settings.agentic_max_retries,
        )


@dataclass
class AgenticBudgetUsage:
    iterations: int = 0
    sql_queries: int = 0
    total_rows: int = 0
    execution_seconds: float = 0
    llm_calls: int = 0
    tokens: int = 0
    retries: int = 0


@dataclass(frozen=True)
class LoopAssessment:
    candidates: tuple[EvidenceRequest, ...]
    gap_analysis: dict[str, Any]
    terminal_state: InvestigationState | None = None
    terminal_reason: str = ""
    llm_calls_used: int = 0
    tokens_used: int = 0

    def __post_init__(self) -> None:
        allowed = {
            None,
            InvestigationState.ROOT_CAUSE_CONFIRMED,
            InvestigationState.ISSUE_NOT_REPRODUCED,
            InvestigationState.INSUFFICIENT_EVIDENCE,
            InvestigationState.BLOCKED_BY_MISSING_SOURCE,
        }
        if self.terminal_state not in allowed:
            raise ValueError("Assessment proposed an unsupported terminal state")


class EvidenceAssessor(Protocol):
    def assess(self, evidence: tuple[EvidenceResult, ...]) -> LoopAssessment: ...


class EvidenceVerifier(Protocol):
    def verify(
        self,
        request: EvidenceRequest,
        evidence: tuple[EvidenceResult, ...],
    ) -> tuple[EvidenceResult, ...]: ...


class AgenticEvidencePipeline(Protocol):
    def plan(self, request: EvidenceRequest) -> tuple[PlannedQuery, ...]: ...

    def validate(self, queries: tuple[PlannedQuery, ...]) -> tuple[PlannedQuery, ...]: ...

    def execute(self, queries: tuple[PlannedQuery, ...]) -> tuple[EvidenceResult, ...]: ...


class PassThroughEvidenceVerifier:
    """Evidence execution already normalizes status and zero-row semantics."""

    def verify(
        self,
        _request: EvidenceRequest,
        evidence: tuple[EvidenceResult, ...],
    ) -> tuple[EvidenceResult, ...]:
        return evidence


class DeterministicSQLPipeline:
    """Adapter from one logical request to the existing deterministic SQL services."""

    def __init__(
        self,
        *,
        connector,
        intent,
        metadata,
        entities,
        provider: Any,
        scan_policy=None,
        workspace_id: str = "",
        connection_id: str = "",
    ):
        self.connector = connector
        self.intent = intent
        self.metadata = metadata
        self.entities = entities
        self.provider = provider
        self.scan_policy = scan_policy
        self.workspace_id = workspace_id
        self.connection_id = connection_id

    def plan(self, request: EvidenceRequest) -> tuple[PlannedQuery, ...]:
        candidates = plan_safe_queries(
            self.intent,
            self.metadata,
            self.entities,
            provider=self.provider,
        )
        selected = _select_query_for_request(request, candidates)
        return (selected,) if selected else ()

    def validate(self, queries: tuple[PlannedQuery, ...]) -> tuple[PlannedQuery, ...]:
        approved: list[PlannedQuery] = []
        for query in queries:
            try:
                validate_read_only_sql(query.sql)
            except ValueError:
                continue
            approved.append(query)
        return tuple(approved)

    def execute(self, queries: tuple[PlannedQuery, ...]) -> tuple[EvidenceResult, ...]:
        return tuple(
            execute_evidence_plan(
                self.connector,
                list(queries),
                provider=self.provider,
                scan_policy=self.scan_policy,
                workspace_id=self.workspace_id,
                connection_id=self.connection_id,
            )
        )


@dataclass(frozen=True)
class AgenticLoopResult:
    terminal_state: InvestigationState
    terminal_reason: str
    evidence: tuple[EvidenceResult, ...]
    budget: AgenticBudgetUsage
    steps: tuple[InvestigationAgenticStepModel, ...] = field(default_factory=tuple)


class MultiStepAgenticInvestigationLoop:
    def __init__(
        self,
        db: Session,
        *,
        assessor: EvidenceAssessor,
        pipeline: AgenticEvidencePipeline,
        policy: EnvironmentPolicy,
        limits: AgenticLoopLimits,
        verifier: EvidenceVerifier | None = None,
        planner: SafeInvestigationPlanner | None = None,
        monotonic=time.monotonic,
    ):
        self.db = db
        self.assessor = assessor
        self.pipeline = pipeline
        self.policy = policy
        self.limits = limits
        self.verifier = verifier or PassThroughEvidenceVerifier()
        self.planner = planner or SafeInvestigationPlanner()
        self.monotonic = monotonic

    def run(
        self,
        investigation: InvestigationModel,
        *,
        initial_evidence: tuple[EvidenceResult, ...] = (),
        is_cancelled=lambda: False,
    ) -> AgenticLoopResult:
        state = InvestigationStateService(self.db)
        current = state.initialize(investigation)
        evidence = list(initial_evidence)
        history: list[PreviousAction] = []
        usage = AgenticBudgetUsage()
        steps: list[InvestigationAgenticStepModel] = []
        started = self.monotonic()

        while True:
            if is_cancelled():
                terminal = state.cancel(investigation, reason="Cancellation requested.")
                return _result(terminal.current_state, terminal.reason, evidence, usage, steps)
            usage.execution_seconds = self.monotonic() - started
            terminal = _budget_terminal(usage, self.limits)
            if terminal and current.current_state is InvestigationState.STOP_EVALUATION:
                transition = state.transition(
                    investigation,
                    terminal[0],
                    reason=terminal[1],
                )
                return _result(
                    transition.current_state,
                    transition.reason,
                    evidence,
                    usage,
                    steps,
                )
            if current.current_state is InvestigationState.STOP_EVALUATION:
                current = state.transition(
                    investigation,
                    InvestigationState.EVIDENCE_ASSESSMENT,
                    reason="Continue with the next controlled evidence iteration.",
                )
            elif current.current_state is InvestigationState.INITIALIZATION:
                current = state.transition(
                    investigation,
                    InvestigationState.EVIDENCE_ASSESSMENT,
                    reason="Assess current verified evidence.",
                )

            try:
                assessment = self.assessor.assess(tuple(evidence))
            except Exception as exc:
                transition = state.fail(
                    investigation,
                    reason=f"Evidence assessment failed: {type(exc).__name__}.",
                )
                return _result(
                    transition.current_state,
                    transition.reason,
                    evidence,
                    usage,
                    steps,
                )
            usage.llm_calls += assessment.llm_calls_used
            usage.tokens += assessment.tokens_used
            if assessment.terminal_state:
                if (
                    assessment.terminal_state
                    is InvestigationState.BLOCKED_BY_MISSING_SOURCE
                ):
                    state.transition(
                        investigation,
                        InvestigationState.GAP_IDENTIFICATION,
                        reason="External evidence gap identified.",
                    )
                terminal_transition = state.transition(
                    investigation,
                    assessment.terminal_state,
                    reason=assessment.terminal_reason,
                )
                return _result(
                    terminal_transition.current_state,
                    terminal_transition.reason,
                    evidence,
                    usage,
                    steps,
                )
            current = state.transition(
                investigation,
                InvestigationState.GAP_IDENTIFICATION,
                reason="Updated unresolved questions from verified evidence.",
            )
            if is_cancelled():
                terminal_transition = state.cancel(
                    investigation, reason="Cancellation requested."
                )
                return _result(
                    terminal_transition.current_state,
                    terminal_transition.reason,
                    evidence,
                    usage,
                    steps,
                )
            current = state.transition(
                investigation,
                InvestigationState.ACTION_SELECTION,
                reason="Select the highest-value safe logical evidence request.",
            )
            decision = self.planner.select_next(
                candidates=assessment.candidates,
                previous_actions=history,
                budget=InvestigationBudget(
                    queries_used=usage.sql_queries,
                    query_limit=self.limits.max_sql_queries,
                    iterations_used=usage.iterations,
                    iteration_limit=self.limits.max_iterations,
                ),
                policy=self.policy,
            )
            self.planner.persist(self.db, investigation=investigation, decision=decision)
            if decision.status is not PlannerStatus.SELECTED:
                terminal_state = _planner_terminal(decision.status, assessment)
                terminal_transition = state.transition(
                    investigation,
                    terminal_state,
                    reason=decision.selection_reason,
                )
                return _result(
                    terminal_transition.current_state,
                    terminal_transition.reason,
                    evidence,
                    usage,
                    steps,
                )

            request = decision.selected_request
            assert request is not None
            if decision.retry_number:
                usage.retries += 1
                if usage.retries > self.limits.max_retries:
                    terminal_transition = state.transition(
                        investigation,
                        InvestigationState.INSUFFICIENT_EVIDENCE,
                        reason="Controlled retry budget exhausted.",
                    )
                    return _result(
                        terminal_transition.current_state,
                        terminal_transition.reason,
                        evidence,
                        usage,
                        steps,
                    )
            current = state.transition(
                investigation,
                InvestigationState.PLANNING,
                reason=f"Plan logical request {decision.action_fingerprint}.",
            )
            step_started = self.monotonic()
            try:
                queries = self.pipeline.plan(request)
            except Exception as exc:
                transition = state.fail(
                    investigation,
                    reason=f"Deterministic SQL planning failed: {type(exc).__name__}.",
                )
                return _result(
                    transition.current_state,
                    transition.reason,
                    evidence,
                    usage,
                    steps,
                )
            if not queries:
                history.append(
                    PreviousAction(
                        decision.action_fingerprint,
                        ActionOutcome.FAILED_PERMANENT,
                    )
                )
                current = state.transition(
                    investigation,
                    InvestigationState.STATE_UPDATE,
                    reason="Deterministic SQL planner produced no approved candidate.",
                )
                step_evidence: tuple[EvidenceResult, ...] = ()
                outcome = "PLANNING_FAILED"
            else:
                current = state.transition(
                    investigation,
                    InvestigationState.VALIDATION,
                    reason="Validate provider-specific SQL as read-only.",
                )
                try:
                    approved = self.pipeline.validate(queries)
                except Exception as exc:
                    transition = state.fail(
                        investigation,
                        reason=f"SQL validation failed: {type(exc).__name__}.",
                    )
                    return _result(
                        transition.current_state,
                        transition.reason,
                        evidence,
                        usage,
                        steps,
                    )
                if not approved:
                    history.append(
                        PreviousAction(
                            decision.action_fingerprint,
                            ActionOutcome.FAILED_PERMANENT,
                        )
                    )
                    current = state.transition(
                        investigation,
                        InvestigationState.STATE_UPDATE,
                        reason="SQL validator approved no query.",
                    )
                    step_evidence = ()
                    outcome = "VALIDATION_REJECTED"
                elif usage.sql_queries + len(approved) > self.limits.max_sql_queries:
                    terminal_transition = state.transition(
                        investigation,
                        InvestigationState.QUERY_BUDGET_EXHAUSTED,
                        reason="Approved SQL would exceed the query budget.",
                    )
                    return _result(
                        terminal_transition.current_state,
                        terminal_transition.reason,
                        evidence,
                        usage,
                        steps,
                    )
                else:
                    current = state.transition(
                        investigation,
                        InvestigationState.EXECUTION,
                        reason="Execute approved read-only SQL.",
                    )
                    if is_cancelled():
                        terminal_transition = state.cancel(
                            investigation, reason="Cancellation requested."
                        )
                        return _result(
                            terminal_transition.current_state,
                            terminal_transition.reason,
                            evidence,
                            usage,
                            steps,
                        )
                    try:
                        raw_evidence = self.pipeline.execute(approved)
                    except Exception as exc:
                        transition = state.fail(
                            investigation,
                            reason=f"Read-only evidence execution failed: {type(exc).__name__}.",
                        )
                        return _result(
                            transition.current_state,
                            transition.reason,
                            evidence,
                            usage,
                            steps,
                        )
                    usage.sql_queries += len(approved)
                    usage.total_rows += sum(item.row_count for item in raw_evidence)
                    current = state.transition(
                        investigation,
                        InvestigationState.VERIFICATION,
                        reason="Normalize and verify deterministic evidence results.",
                    )
                    try:
                        step_evidence = self.verifier.verify(request, raw_evidence)
                    except Exception as exc:
                        transition = state.fail(
                            investigation,
                            reason=f"Evidence verification failed: {type(exc).__name__}.",
                        )
                        return _result(
                            transition.current_state,
                            transition.reason,
                            evidence,
                            usage,
                            steps,
                        )
                    evidence.extend(step_evidence)
                    outcome, action_outcome = _execution_outcome(step_evidence)
                    history.append(
                        PreviousAction(decision.action_fingerprint, action_outcome)
                    )
                    current = state.transition(
                        investigation,
                        InvestigationState.STATE_UPDATE,
                        reason="Persist evidence and cumulative budget usage.",
                    )

            usage.iterations += 1
            usage.execution_seconds = self.monotonic() - started
            step = self._persist_step(
                investigation=investigation,
                iteration=usage.iterations,
                request=request,
                fingerprint=decision.action_fingerprint,
                queries=queries,
                evidence=step_evidence,
                assessment=assessment,
                usage=usage,
                outcome=outcome,
                reason=current.reason,
                duration_ms=int((self.monotonic() - step_started) * 1000),
            )
            steps.append(step)
            current = state.transition(
                investigation,
                InvestigationState.STOP_EVALUATION,
                reason="Re-evaluate deterministic stop conditions.",
            )
            terminal = _budget_terminal(usage, self.limits)
            if terminal:
                terminal_transition = state.transition(
                    investigation,
                    terminal[0],
                    reason=terminal[1],
                )
                return _result(
                    terminal_transition.current_state,
                    terminal_transition.reason,
                    evidence,
                    usage,
                    steps,
                )

    def _persist_step(
        self,
        *,
        investigation: InvestigationModel,
        iteration: int,
        request: EvidenceRequest,
        fingerprint: str,
        queries: tuple[PlannedQuery, ...],
        evidence: tuple[EvidenceResult, ...],
        assessment: LoopAssessment,
        usage: AgenticBudgetUsage,
        outcome: str,
        reason: str,
        duration_ms: int,
    ) -> InvestigationAgenticStepModel:
        row = InvestigationAgenticStepModel(
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            investigation_id=investigation.id,
            iteration_number=iteration,
            state=InvestigationState.STATE_UPDATE.value,
            action_fingerprint=fingerprint,
            evidence_request_json=_json(request),
            planned_queries_json=_json(queries),
            evidence_json=_json(evidence),
            gap_analysis_json=json.dumps(assessment.gap_analysis, sort_keys=True),
            budget_json=_json(usage),
            outcome=outcome,
            reason=reason,
            duration_ms=max(duration_ms, 0),
        )
        self.db.add(row)
        self.db.flush()
        return row


def _select_query_for_request(
    request: EvidenceRequest,
    candidates: list[PlannedQuery],
) -> PlannedQuery | None:
    markers = {
        "ENTITY_LOOKUP": ("entity", "business key", "upstream"),
        "RELATED_RECORDS": ("related", "relationship", "downstream", "join"),
        "STATUS_HISTORY": ("status", "state", "transition"),
        "WORKFLOW_TRACE": ("workflow", "step", "transition"),
        "EXCEPTION_LOOKUP": ("exception", "error", "failure"),
        "DEPENDENCY_INSPECTION": ("dependency", "procedure", "trigger", "function"),
        "JOB_HISTORY": ("job", "schedule"),
        "TEMPORAL_CORRELATION": ("time", "date", "created", "updated"),
        "COUNT": ("count", "summary"),
        "VERIFIED_ABSENCE": ("missing", "absence", "not exist"),
        "DUPLICATES": ("duplicate",),
        "REFERENTIAL_INTEGRITY": ("orphan", "foreign", "related"),
        "EXPECTED_STATE_CHECK": ("expected", "status", "state"),
    }
    wanted = markers.get(request.request_type.value, (request.request_type.value.casefold(),))
    return next(
        (
            query
            for query in candidates
            if any(marker in query.purpose.casefold() for marker in wanted)
        ),
        candidates[0] if candidates else None,
    )


def _execution_outcome(
    evidence: tuple[EvidenceResult, ...],
) -> tuple[str, ActionOutcome]:
    if evidence and all(item.execution_status == "succeeded" for item in evidence):
        return "SUCCEEDED", ActionOutcome.SUCCEEDED
    if any(item.execution_status == "timed_out" for item in evidence):
        return "FAILED_TRANSIENT", ActionOutcome.FAILED_TRANSIENT
    return "FAILED_PERMANENT", ActionOutcome.FAILED_PERMANENT


def _budget_terminal(
    usage: AgenticBudgetUsage,
    limits: AgenticLoopLimits,
) -> tuple[InvestigationState, str] | None:
    if usage.iterations >= limits.max_iterations:
        return (
            InvestigationState.ITERATION_BUDGET_EXHAUSTED,
            f"Iteration budget exhausted at {usage.iterations}/{limits.max_iterations}.",
        )
    if usage.sql_queries >= limits.max_sql_queries:
        return (
            InvestigationState.QUERY_BUDGET_EXHAUSTED,
            f"SQL query budget exhausted at {usage.sql_queries}/{limits.max_sql_queries}.",
        )
    if usage.total_rows >= limits.max_total_rows:
        return (
            InvestigationState.QUERY_BUDGET_EXHAUSTED,
            f"Total row budget exhausted at {usage.total_rows}/{limits.max_total_rows}.",
        )
    if usage.execution_seconds >= limits.max_execution_seconds:
        return (
            InvestigationState.ITERATION_BUDGET_EXHAUSTED,
            "Execution-duration budget exhausted.",
        )
    if usage.llm_calls > limits.max_llm_calls:
        return (
            InvestigationState.ITERATION_BUDGET_EXHAUSTED,
            "LLM-call budget exhausted.",
        )
    if usage.tokens > limits.max_tokens:
        return (
            InvestigationState.ITERATION_BUDGET_EXHAUSTED,
            "Token budget exhausted.",
        )
    return None


def _planner_terminal(
    status: PlannerStatus,
    assessment: LoopAssessment,
) -> InvestigationState:
    if status is PlannerStatus.QUERY_BUDGET_EXHAUSTED:
        return InvestigationState.QUERY_BUDGET_EXHAUSTED
    if status is PlannerStatus.ITERATION_BUDGET_EXHAUSTED:
        return InvestigationState.ITERATION_BUDGET_EXHAUSTED
    if status is PlannerStatus.POLICY_BLOCKED:
        return InvestigationState.POLICY_BLOCKED
    gaps = assessment.gap_analysis.get("gaps", [])
    if gaps and all(gap.get("source_type") == "EXTERNAL" for gap in gaps):
        return InvestigationState.BLOCKED_BY_MISSING_SOURCE
    return InvestigationState.INSUFFICIENT_EVIDENCE


def _json(value: Any) -> str:
    def encode(item: Any) -> Any:
        if isinstance(item, StrEnum):
            return item.value
        if is_dataclass(item) and not isinstance(item, type):
            return asdict(item)
        return str(item)

    return json.dumps(
        asdict(value) if hasattr(value, "__dataclass_fields__") else value,
        default=encode,
        sort_keys=True,
    )


def _result(
    state: InvestigationState,
    reason: str,
    evidence: list[EvidenceResult],
    usage: AgenticBudgetUsage,
    steps: list[InvestigationAgenticStepModel],
) -> AgenticLoopResult:
    return AgenticLoopResult(state, reason, tuple(evidence), usage, tuple(steps))
