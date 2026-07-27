from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy.orm import Session

from legacydb_copilot.db.models import ExecutionPathTraceModel, InvestigationModel
from legacydb_copilot.services.audit_service import record_audit_event


class ExecutionSourceType(StrEnum):
    ENTITY_RECORD = "ENTITY_RECORD"
    STATUS_HISTORY = "STATUS_HISTORY"
    WORKFLOW = "WORKFLOW"
    PROCEDURE = "PROCEDURE"
    TRIGGER = "TRIGGER"
    FUNCTION = "FUNCTION"
    JOB = "JOB"
    EXCEPTION = "EXCEPTION"


class TraceVerificationLabel(StrEnum):
    RUNTIME_VERIFIED = "RUNTIME_VERIFIED"
    DATA_STATE_VERIFIED = "DATA_STATE_VERIFIED"
    METADATA_ONLY = "METADATA_ONLY"
    INFERRED_UNVERIFIED = "INFERRED_BUT_UNVERIFIED"
    MISSING = "MISSING"
    CONTRADICTORY = "CONTRADICTORY"


@dataclass(frozen=True)
class ExpectedPathStep:
    step_id: str
    name: str
    sequence: int
    expected_state: str
    expected_component: str = ""


@dataclass(frozen=True)
class ExecutionObservation:
    step_id: str
    source_type: ExecutionSourceType
    state: str
    evidence_refs: tuple[str, ...]
    timestamp: datetime | None = None
    component: str = ""
    runtime_verified: bool = False
    data_state_verified: bool = False
    metadata_only: bool = False
    inferred: bool = False


@dataclass(frozen=True)
class ExecutionTimelineNode:
    step_id: str
    name: str
    sequence: int
    expected_state: str
    actual_state: str
    component: str
    verification_label: TraceVerificationLabel
    outcome: str
    timestamp: datetime | None
    evidence_refs: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ExecutionTimelineEdge:
    source_step_id: str
    target_step_id: str
    verification_label: TraceVerificationLabel
    evidence_refs: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ExecutionPathTrace:
    affected_entity: str
    expected_path: tuple[str, ...]
    nodes: tuple[ExecutionTimelineNode, ...]
    edges: tuple[ExecutionTimelineEdge, ...]
    verified_completed_steps: tuple[str, ...]
    last_successful_step: str
    first_failed_or_missing_step: str
    responsible_component: str
    remaining_gap: str
    status: str

    def report_timeline(self) -> list[dict[str, str]]:
        return [
            {
                "sequence": str(node.sequence),
                "step": node.name,
                "expected_state": node.expected_state,
                "actual_state": node.actual_state,
                "verification": node.verification_label.value,
                "outcome": node.outcome,
                "component": node.component,
                "timestamp": node.timestamp.isoformat() if node.timestamp else "",
                "evidence_refs": ", ".join(node.evidence_refs),
                "reason": node.reason,
            }
            for node in self.nodes
        ]


class ExecutionPathTracingService:
    def trace(
        self,
        *,
        affected_entity: str,
        expected_steps: Iterable[ExpectedPathStep],
        observations: Iterable[ExecutionObservation],
    ) -> ExecutionPathTrace:
        ordered = tuple(sorted(expected_steps, key=lambda item: (item.sequence, item.step_id)))
        if not ordered:
            raise ValueError("At least one expected processing step is required")
        if len({item.step_id for item in ordered}) != len(ordered):
            raise ValueError("Expected processing step identifiers must be unique")
        grouped: dict[str, list[ExecutionObservation]] = {}
        for observation in observations:
            grouped.setdefault(observation.step_id, []).append(observation)

        nodes: list[ExecutionTimelineNode] = []
        previous_timestamp: datetime | None = None
        for step in ordered:
            node = _build_node(step, grouped.get(step.step_id, ()))
            if (
                previous_timestamp is not None
                and node.timestamp is not None
                and node.timestamp < previous_timestamp
            ):
                node = ExecutionTimelineNode(
                    **{
                        **asdict(node),
                        "verification_label": TraceVerificationLabel.CONTRADICTORY,
                        "outcome": "INCONSISTENT",
                        "reason": "Timestamp precedes the prior verified processing step.",
                    }
                )
            if (
                node.timestamp is not None
                and node.verification_label
                in {
                    TraceVerificationLabel.RUNTIME_VERIFIED,
                    TraceVerificationLabel.DATA_STATE_VERIFIED,
                }
            ):
                previous_timestamp = node.timestamp
            nodes.append(node)

        edges = tuple(
            _build_edge(source, target)
            for source, target in zip(nodes, nodes[1:], strict=False)
        )
        completed: list[str] = []
        first_problem = ""
        last_successful = ""
        responsible_component = ""
        remaining_gap = ""
        for node in nodes:
            verified = node.verification_label in {
                TraceVerificationLabel.RUNTIME_VERIFIED,
                TraceVerificationLabel.DATA_STATE_VERIFIED,
            }
            successful = node.outcome == "COMPLETED"
            if not first_problem and verified and successful:
                completed.append(node.step_id)
                last_successful = node.step_id
                continue
            if not first_problem:
                first_problem = node.step_id
                if (
                    node.component
                    and node.verification_label
                    in {
                        TraceVerificationLabel.RUNTIME_VERIFIED,
                        TraceVerificationLabel.DATA_STATE_VERIFIED,
                        TraceVerificationLabel.CONTRADICTORY,
                    }
                ):
                    responsible_component = node.component
                remaining_gap = _remaining_gap(node)

        status = "COMPLETE" if not first_problem else "GAP_IDENTIFIED"
        return ExecutionPathTrace(
            affected_entity=affected_entity.strip(),
            expected_path=tuple(item.step_id for item in ordered),
            nodes=tuple(nodes),
            edges=edges,
            verified_completed_steps=tuple(completed),
            last_successful_step=last_successful,
            first_failed_or_missing_step=first_problem,
            responsible_component=responsible_component,
            remaining_gap=remaining_gap,
            status=status,
        )

    def persist(
        self,
        db: Session,
        *,
        investigation: InvestigationModel,
        trace: ExecutionPathTrace,
    ) -> ExecutionPathTraceModel:
        row = ExecutionPathTraceModel(
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            investigation_id=investigation.id,
            affected_entity=trace.affected_entity,
            status=trace.status,
            expected_path_json=json.dumps(trace.expected_path),
            nodes_json=json.dumps([asdict(item) for item in trace.nodes], default=_json_default),
            edges_json=json.dumps([asdict(item) for item in trace.edges], default=_json_default),
            verified_completed_steps_json=json.dumps(trace.verified_completed_steps),
            last_successful_step=trace.last_successful_step,
            first_failed_or_missing_step=trace.first_failed_or_missing_step,
            responsible_component=trace.responsible_component,
            remaining_gap=trace.remaining_gap,
        )
        db.add(row)
        db.flush()
        record_audit_event(
            db,
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            user_id=investigation.created_by_id,
            action="EXECUTION_PATH_TRACED",
            resource_type="investigation",
            resource_id=investigation.id,
            metadata={
                "affected_entity": trace.affected_entity,
                "status": trace.status,
                "last_successful_step": trace.last_successful_step,
                "first_failed_or_missing_step": trace.first_failed_or_missing_step,
                "responsible_component": trace.responsible_component,
            },
        )
        return row


def _build_node(
    step: ExpectedPathStep,
    observations: Iterable[ExecutionObservation],
) -> ExecutionTimelineNode:
    items = tuple(observations)
    refs = tuple(dict.fromkeys(ref for item in items for ref in item.evidence_refs))
    states = tuple(dict.fromkeys(item.state.strip() for item in items if item.state.strip()))
    components = tuple(
        dict.fromkeys(item.component.strip() for item in items if item.component.strip())
    )
    timestamps = tuple(sorted(item.timestamp for item in items if item.timestamp is not None))
    if not items:
        label = TraceVerificationLabel.MISSING
        reason = "No evidence was supplied for this expected processing step."
    elif len({state.casefold() for state in states}) > 1:
        label = TraceVerificationLabel.CONTRADICTORY
        reason = "Evidence reports contradictory states for this processing step."
    elif any(item.runtime_verified for item in items):
        label = TraceVerificationLabel.RUNTIME_VERIFIED
        reason = "Runtime execution evidence verifies this processing step."
    elif any(item.data_state_verified for item in items):
        label = TraceVerificationLabel.DATA_STATE_VERIFIED
        reason = "Persisted data state verifies this processing step."
    elif all(item.metadata_only for item in items):
        label = TraceVerificationLabel.METADATA_ONLY
        reason = "Object definition or dependency metadata exists but does not prove execution."
    elif any(item.inferred for item in items):
        label = TraceVerificationLabel.INFERRED_UNVERIFIED
        reason = "The step is inferred but lacks runtime or data-state proof."
    else:
        label = TraceVerificationLabel.INFERRED_UNVERIFIED
        reason = "Evidence does not independently verify this processing step."
    actual_state = " / ".join(states)
    failed = any(
        marker in actual_state.casefold()
        for marker in ("fail", "error", "exception", "missing", "rejected", "cancel")
    )
    completed = any(
        marker in actual_state.casefold()
        for marker in (
            "success",
            "succeeded",
            "complete",
            "completed",
            "ready",
            "posted",
            "delivered",
        )
    )
    outcome = (
        "FAILED"
        if failed
        else "COMPLETED"
        if completed
        else "INCONSISTENT"
        if label is TraceVerificationLabel.CONTRADICTORY
        else "UNVERIFIED"
    )
    return ExecutionTimelineNode(
        step_id=step.step_id,
        name=step.name,
        sequence=step.sequence,
        expected_state=step.expected_state,
        actual_state=actual_state,
        component=components[0] if len(components) == 1 else "",
        verification_label=label,
        outcome=outcome,
        timestamp=timestamps[-1] if timestamps else None,
        evidence_refs=refs,
        reason=reason,
    )


def _build_edge(
    source: ExecutionTimelineNode,
    target: ExecutionTimelineNode,
) -> ExecutionTimelineEdge:
    refs = tuple(dict.fromkeys((*source.evidence_refs, *target.evidence_refs)))
    labels = {source.verification_label, target.verification_label}
    if TraceVerificationLabel.CONTRADICTORY in labels:
        label = TraceVerificationLabel.CONTRADICTORY
        reason = "At least one endpoint has contradictory evidence."
    elif labels <= {
        TraceVerificationLabel.RUNTIME_VERIFIED,
        TraceVerificationLabel.DATA_STATE_VERIFIED,
    }:
        label = (
            TraceVerificationLabel.RUNTIME_VERIFIED
            if labels == {TraceVerificationLabel.RUNTIME_VERIFIED}
            else TraceVerificationLabel.DATA_STATE_VERIFIED
        )
        reason = "Both endpoint states are verified in the expected order."
    elif TraceVerificationLabel.MISSING in labels:
        label = TraceVerificationLabel.MISSING
        reason = "The transition cannot be verified because an endpoint is missing."
    elif TraceVerificationLabel.METADATA_ONLY in labels:
        label = TraceVerificationLabel.METADATA_ONLY
        reason = "Metadata establishes a possible dependency, not runtime execution."
    else:
        label = TraceVerificationLabel.INFERRED_UNVERIFIED
        reason = "The transition remains inferred but unverified."
    return ExecutionTimelineEdge(
        source_step_id=source.step_id,
        target_step_id=target.step_id,
        verification_label=label,
        evidence_refs=refs,
        reason=reason,
    )


def _remaining_gap(node: ExecutionTimelineNode) -> str:
    if node.verification_label is TraceVerificationLabel.METADATA_ONLY:
        return f"Runtime execution proof is missing for {node.name}."
    if node.verification_label is TraceVerificationLabel.CONTRADICTORY:
        return f"Contradictory evidence must be resolved for {node.name}."
    if node.verification_label is TraceVerificationLabel.MISSING:
        return f"Evidence is missing for expected step {node.name}."
    if node.outcome == "FAILED":
        return f"Causal evidence is still required for failed step {node.name}."
    return f"Runtime or data-state verification is required for {node.name}."


def _json_default(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
