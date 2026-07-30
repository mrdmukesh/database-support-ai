from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, TypeAlias

from legacydb_copilot.workflow.langgraph.state import InvestigationState

NodeResult: TypeAlias = Mapping[str, Any]
NodeHandler: TypeAlias = Callable[[InvestigationState], NodeResult]


class InvestigationNode(Protocol):
    def __call__(self, state: InvestigationState) -> NodeResult: ...


@dataclass(frozen=True)
class InvestigationWorkflowHandlers:
    initialize: NodeHandler
    resolve_entity: NodeHandler
    discover_objects: NodeHandler
    create_plan: NodeHandler
    validate_sql: NodeHandler
    execute_sql: NodeHandler
    preserve_evidence: NodeHandler
    assess_evidence: NodeHandler
    compose_report: NodeHandler
    finalize: NodeHandler


@dataclass(frozen=True)
class EvidenceDrivenWorkflowHandlers:
    initialize: NodeHandler
    resolve_entity: NodeHandler
    discover_objects: NodeHandler
    create_plan: NodeHandler
    validate_sql: NodeHandler
    execute_sql: NodeHandler
    preserve_evidence: NodeHandler
    classify_results: NodeHandler
    check_coverage: NodeHandler
    assess_evidence: NodeHandler
    compose_report: NodeHandler
    finalize: NodeHandler


@dataclass(frozen=True)
class NodeTelemetryEvent:
    investigation_id: str
    node_name: str
    event_type: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: float | None
    success: bool | None
    error_code: str
    workflow_iteration: int
    planning_round: int = 0
    query_id: str = ""
    plan_step_id: str = ""
    validation_outcome: str = ""
    execution_outcome: str = ""
    evidence_id: str = ""
    evidence_classification: str = ""
    coverage_percentage: float = 0.0
    missing_object_count: int = 0
    replan_reason: str = ""
    limit_reached: bool = False
    no_progress_detected: bool = False


class TelemetryRecorder(Protocol):
    def record(self, event: NodeTelemetryEvent) -> None: ...


class NullTelemetryRecorder:
    def record(self, _event: NodeTelemetryEvent) -> None:
        return


@dataclass
class InMemoryTelemetryRecorder:
    events: list[NodeTelemetryEvent] = field(default_factory=list)

    def record(self, event: NodeTelemetryEvent) -> None:
        self.events.append(event)


class OperationalNodeError(RuntimeError):
    """Expected dependency or policy failure safe to represent in workflow state."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.context = context or {}
