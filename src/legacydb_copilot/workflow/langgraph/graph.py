from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from legacydb_copilot.workflow.langgraph.adapters.coverage import coverage_route
from legacydb_copilot.workflow.langgraph.contracts import (
    EvidenceDrivenWorkflowHandlers,
    InvestigationWorkflowHandlers,
    NodeHandler,
    NodeTelemetryEvent,
    NullTelemetryRecorder,
    OperationalNodeError,
    TelemetryRecorder,
)
from legacydb_copilot.workflow.langgraph.enums import WorkflowTerminalStatus
from legacydb_copilot.workflow.langgraph.state import (
    ErrorRecord,
    InvestigationState,
    deserialize_investigation_state,
    serialize_investigation_state,
)

NODE_ORDER = (
    "initialize",
    "resolve_entity",
    "discover_objects",
    "create_plan",
    "validate_sql",
    "execute_sql",
    "preserve_evidence",
    "assess_evidence",
    "compose_report",
    "finalize",
)
EDGE_SEQUENCE = tuple(zip((START, *NODE_ORDER), (*NODE_ORDER, END), strict=True))
EVIDENCE_NODE_ORDER = (
    "initialize",
    "resolve_entity",
    "discover_objects",
    "create_plan",
    "validate_sql",
    "execute_sql",
    "preserve_evidence",
    "classify_results",
    "check_coverage",
    "assess_evidence",
    "compose_report",
    "finalize",
)
IDENTITY_FIELDS = frozenset({"investigation_id", "workspace_id", "correlation_id", "question"})
TERMINAL_FAILURES = frozenset(
    {
        WorkflowTerminalStatus.CANCELLED,
        WorkflowTerminalStatus.FAILED,
        WorkflowTerminalStatus.ENTITY_NOT_FOUND,
        WorkflowTerminalStatus.AMBIGUOUS_ENTITY,
    }
)


def _wall_clock() -> datetime:
    return datetime.now(UTC)


def _validate_initialize_state(state: InvestigationState) -> None:
    for field_name in ("investigation_id", "workspace_id", "question"):
        if not str(state[field_name]).strip():
            raise ValueError(f"{field_name} is required")
    for field_name in ("workflow_iteration", "planning_round", "query_count", "object_count"):
        if state[field_name] < 0:
            raise ValueError(f"{field_name} cannot be negative")


def _validated_update(
    state: InvestigationState,
    update: dict[str, Any],
    *,
    node_name: str,
) -> dict[str, Any]:
    unknown = set(update) - set(state)
    if unknown:
        raise ValueError(f"Node {node_name} returned unknown state fields: {sorted(unknown)}")
    changed_identity = {
        field_name
        for field_name in IDENTITY_FIELDS & set(update)
        if update[field_name] != state[field_name]
    }
    if changed_identity:
        raise ValueError(
            f"Node {node_name} attempted to change investigation identity: "
            f"{sorted(changed_identity)}"
        )
    candidate = dict(state)
    candidate.update(update)
    deserialize_investigation_state(serialize_investigation_state(candidate))
    return update


def _event(
    *,
    state: InvestigationState,
    node_name: str,
    event_type: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    duration_ms: float | None = None,
    success: bool | None = None,
    error_code: str = "",
) -> NodeTelemetryEvent:
    query = (
        state["query_results"][-1]
        if state["query_results"]
        else state["approved_queries"][-1]
        if state["approved_queries"]
        else state["rejected_queries"][-1]
        if state["rejected_queries"]
        else None
    )
    finding = state["findings"][-1] if state["findings"] else None
    return NodeTelemetryEvent(
        investigation_id=state["investigation_id"],
        node_name=node_name,
        event_type=event_type,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        success=success,
        error_code=error_code,
        workflow_iteration=state["workflow_iteration"],
        planning_round=state["planning_round"],
        query_id=query.query_id if query else "",
        plan_step_id=query.plan_step_id if query else "",
        validation_outcome=query.validation_status.value if query else "",
        execution_outcome=query.execution_status.value if query else "",
        evidence_id=query.evidence_id if query else "",
        evidence_classification=finding.finding_type.value if finding else "",
        coverage_percentage=state["coverage_percentage"],
        missing_object_count=len(state["missing_required_objects"]),
        replan_reason=state["replan_reason"],
        limit_reached=state["coverage_status"].value == "LIMIT_REACHED",
        no_progress_detected=state["no_progress_rounds"] >= state["no_progress_limit"],
    )


def wrap_node(
    node_name: str,
    handler: NodeHandler,
    *,
    telemetry: TelemetryRecorder,
    monotonic: Callable[[], float] = time.monotonic,
    wall_clock: Callable[[], datetime] = _wall_clock,
) -> NodeHandler:
    """Apply validation, tracking, telemetry, and explicit failure policy to one handler."""

    def wrapped(state: InvestigationState) -> dict[str, Any]:
        if state["terminal_status"] in TERMINAL_FAILURES:
            return {}
        if state["cancel_requested"] and node_name not in {"initialize", "finalize"}:
            return {
                "previous_node": state["current_node"],
                "current_node": node_name,
                "updated_at": wall_clock(),
                "stop_reason": "Cancellation requested.",
                "terminal_status": WorkflowTerminalStatus.CANCELLED,
            }
        if node_name == "initialize":
            _validate_initialize_state(state)

        started_at = wall_clock()
        started = monotonic()
        telemetry.record(
            _event(
                state=state,
                node_name=node_name,
                event_type="started",
                started_at=started_at,
            )
        )
        tracking = {
            "previous_node": state["current_node"],
            "current_node": node_name,
            "updated_at": started_at,
        }
        safe_input = deserialize_investigation_state(serialize_investigation_state(state))
        try:
            handler_update = dict(handler(safe_input))
            update = {**handler_update, **tracking}
            if node_name == "initialize":
                update["terminal_status"] = WorkflowTerminalStatus.RUNNING
            validated = _validated_update(state, update, node_name=node_name)
        except OperationalNodeError as exc:
            finished_at = wall_clock()
            duration_ms = max(0.0, (monotonic() - started) * 1000)
            error = ErrorRecord.from_exception(
                source_node=node_name,
                code=exc.code,
                exception=exc,
                retryable=exc.retryable,
                context=exc.context,
                timestamp=finished_at,
            )
            telemetry.record(
                _event(
                    state=state,
                    node_name=node_name,
                    event_type="finished",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    success=False,
                    error_code=exc.code,
                )
            )
            return {
                **tracking,
                "updated_at": finished_at,
                "errors": [*state["errors"], error],
                "stop_reason": error.message,
                "terminal_status": WorkflowTerminalStatus.FAILED,
            }
        except Exception as exc:
            finished_at = wall_clock()
            duration_ms = max(0.0, (monotonic() - started) * 1000)
            telemetry.record(
                _event(
                    state=state,
                    node_name=node_name,
                    event_type="finished",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    success=False,
                    error_code=type(exc).__name__,
                )
            )
            raise

        finished_at = wall_clock()
        duration_ms = max(0.0, (monotonic() - started) * 1000)
        validated["updated_at"] = finished_at
        telemetry.record(
            _event(
                state=state,
                node_name=node_name,
                event_type="finished",
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                success=True,
            )
        )
        return validated

    return wrapped


def build_investigation_graph(
    handlers: InvestigationWorkflowHandlers,
    *,
    telemetry: TelemetryRecorder | None = None,
):
    """Compile the isolated linear graph; construction performs no service or network I/O."""
    recorder = telemetry or NullTelemetryRecorder()
    builder = StateGraph(InvestigationState)
    for node_name in NODE_ORDER:
        builder.add_node(
            node_name,
            wrap_node(node_name, getattr(handlers, node_name), telemetry=recorder),
        )
    for source, target in EDGE_SEQUENCE:
        builder.add_edge(source, target)
    return builder.compile()


def build_evidence_driven_graph(
    handlers: EvidenceDrivenWorkflowHandlers,
    *,
    telemetry: TelemetryRecorder | None = None,
):
    """Compile the isolated bounded evidence loop without production activation."""
    recorder = telemetry or NullTelemetryRecorder()
    builder = StateGraph(InvestigationState)
    for node_name in EVIDENCE_NODE_ORDER:
        builder.add_node(
            node_name,
            wrap_node(node_name, getattr(handlers, node_name), telemetry=recorder),
        )
    linear = (
        (START, "initialize"),
        ("initialize", "resolve_entity"),
        ("resolve_entity", "discover_objects"),
        ("discover_objects", "create_plan"),
        ("create_plan", "validate_sql"),
        ("validate_sql", "execute_sql"),
        ("execute_sql", "preserve_evidence"),
        ("preserve_evidence", "classify_results"),
        ("classify_results", "check_coverage"),
    )
    for source, target in linear:
        builder.add_edge(source, target)
    builder.add_conditional_edges(
        "check_coverage",
        coverage_route,
        {
            "create_plan": "create_plan",
            "assess_evidence": "assess_evidence",
            "finalize": "finalize",
        },
    )
    builder.add_edge("assess_evidence", "compose_report")
    builder.add_edge("compose_report", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile()
