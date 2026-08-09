from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator
from typing_extensions import TypedDict

from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.pii_masking_service import sanitize_ai_trace
from legacydb_copilot.workflow.langgraph.enums import (
    CandidateStatus,
    CoverageStatus,
    EntityResolutionStatus,
    EvidenceOutcome,
    ObjectDisposition,
    QueryExecutionStatus,
    QueryValidationStatus,
    RelationshipVerification,
    WorkflowReasoningMode,
    WorkflowReproductionStatus,
    WorkflowTerminalStatus,
)


class StateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EnvironmentPolicyRecord(StateRecord):
    environment_type: str = ""
    policy_name: str = ""
    policy_version: str = ""
    safety_profile: str = ""
    max_rows: int | None = Field(default=None, ge=0)
    query_timeout_seconds: float | None = Field(default=None, ge=0)
    allow_full_table_scan: bool = False


class EntityCandidateRecord(StateRecord):
    entity_type: str
    business_key: str = ""
    matched_value: str = ""
    database: str = ""
    schema_name: str = ""
    table: str = ""
    column: str = ""
    matching_method: str = ""
    deterministic_rank: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    verified: bool = False
    evidence_id: str = ""


class ResolvedEntityRecord(EntityCandidateRecord):
    verified: bool = True


class DatabaseObjectRef(StateRecord):
    database: str = ""
    schema_name: str = ""
    object_name: str
    object_type: str
    relevance_reason: str = ""
    dependency_distance: int = Field(default=0, ge=0)
    disposition: ObjectDisposition = ObjectDisposition.PLANNED
    relationship_verification: RelationshipVerification | None = None
    inspection_only: bool = False
    contains_mutation: bool = False
    contains_dynamic_sql: bool = False
    unsafe_to_execute: bool = False
    path_role: str = "UNKNOWN"

    @property
    def qualified_name(self) -> str:
        parts = (self.database, self.schema_name, self.object_name)
        return ".".join(part for part in parts if part)


class CandidateObjectRecord(StateRecord):
    candidate_id: str
    object_type: str
    object_name: str
    schema_name: str = ""
    rank: int = Field(ge=1)
    score: float = 0.0
    lexical_relevance: float = 0.0
    semantic_relevance: float = 0.0
    knowledge_relevance: float = 0.0
    structural_relevance: float = 0.0
    path_role: str = "UNKNOWN"
    entity_probe_result: str = "NOT_PROBED"
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    attempt_count: int = Field(default=0, ge=0)
    decision_reason: str = ""
    status: CandidateStatus = CandidateStatus.UNVERIFIED

    @property
    def qualified_name(self) -> str:
        return ".".join(part for part in (self.schema_name, self.object_name) if part)


class RelationshipEdge(StateRecord):
    source_object: str
    source_column: str
    target_object: str
    target_column: str
    relationship_type: str
    verification: RelationshipVerification
    source: str
    evidence_ids: tuple[str, ...] = ()


class InvestigationPlanStep(StateRecord):
    step_id: str
    objective: str
    database: str = ""
    object_name: str = ""
    object_type: str = ""
    evidence_sought: str
    query_intent: str = ""
    dependencies: tuple[str, ...] = ()
    required: bool = True
    success_condition: str = ""
    status: ObjectDisposition = ObjectDisposition.PLANNED
    failure_reason: str = ""
    join_justification: str = ""
    relationship_source: str = ""
    required_objects: tuple[str, ...] = ()
    expected_evidence: str = ""
    validation_status: QueryValidationStatus = QueryValidationStatus.NOT_VALIDATED
    inspection_only: bool = False
    planning_round: int = Field(default=0, ge=0)
    action_fingerprint: str = ""


_PROHIBITED_CONTEXT_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "connection_string",
    "database_url",
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
}


def _sanitized_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return sanitize_ai_trace(value)


class QueryRecord(StateRecord):
    query_id: str
    plan_step_id: str
    sanitized_sql: str = ""
    query_hash: str = ""
    parameter_metadata: dict[str, str] = Field(default_factory=dict)
    validation_status: QueryValidationStatus = QueryValidationStatus.NOT_VALIDATED
    rejection_reason: str = ""
    mutation_classification: str = ""
    execution_status: QueryExecutionStatus = QueryExecutionStatus.NOT_EXECUTED
    row_count: int = Field(default=0, ge=0)
    timed_out: bool = False
    execution_duration_ms: int = Field(default=0, ge=0)
    error_classification: str = ""
    evidence_id: str = ""
    target_database: str = ""
    referenced_objects: tuple[str, ...] = ()
    read_only: bool = False
    rejection_code: str = ""
    validated_at: datetime | None = None
    truncated: bool = False
    result_reference: str = ""
    result_summary: tuple[dict[str, Any], ...] = ()
    executed_at: datetime | None = None

    @field_validator("rejection_reason", "error_classification")
    @classmethod
    def sanitize_diagnostic_text(cls, value: str) -> str:
        return str(sanitize_ai_trace(value))

    @field_validator("result_summary")
    @classmethod
    def sanitize_result_summary(
        cls, value: tuple[dict[str, Any], ...]
    ) -> tuple[dict[str, Any], ...]:
        sanitized: list[dict[str, Any]] = []
        for row in value[:5]:
            safe_row = _sanitized_mapping(row)
            sanitized.append(
                {
                    str(key)[:128]: item
                    if item is None or isinstance(item, (bool, int, float))
                    else str(item)[:500]
                    for key, item in safe_row.items()
                }
            )
        return tuple(sanitized)

    @field_validator("parameter_metadata")
    @classmethod
    def reject_secret_parameter_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        prohibited = {key.casefold() for key in value} & _PROHIBITED_CONTEXT_KEYS
        if prohibited:
            raise ValueError("Secret parameter names are prohibited in workflow state")
        return value


class EvidenceGapRecord(StateRecord):
    gap_type: str
    description: str
    affected_entity: str = ""
    affected_object: str = ""
    blocking: bool = False
    next_recommended_step: str = ""
    source_node: str
    timestamp: datetime
    evidence_ids: tuple[str, ...] = ()


class ClaimEvidenceLink(StateRecord):
    claim_id: str
    evidence_ids: tuple[str, ...]


class FindingRecord(StateRecord):
    finding_type: EvidenceOutcome
    object_name: str = ""
    column_name: str = ""
    description: str
    blocking: bool = False
    evidence_ids: tuple[str, ...] = ()


class ErrorRecord(StateRecord):
    source_node: str
    code: str
    message: str
    retryable: bool = False
    timestamp: datetime
    sanitized_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, value: str) -> str:
        return str(sanitize_ai_trace(value))

    @field_validator("sanitized_context")
    @classmethod
    def sanitize_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _sanitized_mapping(value)

    @classmethod
    def from_exception(
        cls,
        *,
        source_node: str,
        code: str,
        exception: Exception,
        retryable: bool = False,
        context: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ErrorRecord:
        return cls(
            source_node=source_node,
            code=code,
            message=str(exception),
            retryable=retryable,
            timestamp=timestamp or datetime.now(UTC),
            sanitized_context=context or {},
        )


class InvestigationState(TypedDict):
    # Identity
    investigation_id: str
    workspace_id: str
    actor_id: str
    correlation_id: str
    created_at: datetime
    updated_at: datetime
    # Request context
    question: str
    environment: str
    environment_policy: EnvironmentPolicyRecord
    requested_database: str
    requested_entity: str
    requested_objects: list[str]
    investigation_intent: InvestigationIntent
    # Workflow control
    current_node: str
    previous_node: str
    workflow_iteration: Annotated[int, Field(ge=0)]
    planning_round: Annotated[int, Field(ge=0)]
    query_count: Annotated[int, Field(ge=0)]
    object_count: Annotated[int, Field(ge=0)]
    started_at: datetime
    deadline_at: datetime | None
    cancel_requested: bool
    stop_reason: str
    terminal_status: WorkflowTerminalStatus
    # Entity resolution
    entity_resolution_status: EntityResolutionStatus
    resolved_entities: list[ResolvedEntityRecord]
    entity_candidates: list[EntityCandidateRecord]
    entity_resolution_method: str
    entity_resolution_explanation: str
    entity_ambiguities: list[str]
    # Database object discovery
    candidate_objects: list[DatabaseObjectRef]
    ranked_candidates: list[CandidateObjectRecord]
    active_candidate_id: str
    backtrack_count: int
    expansion_count: int
    graph_step_count: int
    max_backtracks: int
    max_expansions: int
    max_candidate_tables: int
    max_candidate_columns: int
    max_candidate_code_objects: int
    max_graph_steps: int
    candidate_transition_trace: list[dict[str, Any]]
    selected_objects: list[DatabaseObjectRef]
    required_objects: list[DatabaseObjectRef]
    optional_objects: list[DatabaseObjectRef]
    relationship_edges: list[RelationshipEdge]
    metadata_gaps: list[EvidenceGapRecord]
    # Plan
    investigation_plan: list[InvestigationPlanStep]
    completed_plan_steps: list[str]
    failed_plan_steps: list[str]
    skipped_plan_steps: list[str]
    # SQL
    proposed_queries: list[QueryRecord]
    approved_queries: list[QueryRecord]
    rejected_queries: list[QueryRecord]
    query_results: list[QueryRecord]
    plan_fingerprints: list[str]
    rejected_query_hashes: list[str]
    no_progress_rounds: int
    replan_reason: str
    max_planning_rounds: int
    max_queries: int
    max_objects: int
    no_progress_limit: int
    # Evidence
    evidence_ids: list[str]
    verified_evidence_ids: list[str]
    unverified_evidence_ids: list[str]
    evidence_gaps: list[EvidenceGapRecord]
    claim_evidence_links: list[ClaimEvidenceLink]
    findings: list[FindingRecord]
    # Coverage
    coverage_status: CoverageStatus
    inspected_objects: list[str]
    successful_objects: list[str]
    failed_objects: list[str]
    skipped_objects: list[str]
    inaccessible_objects: list[str]
    missing_required_objects: list[str]
    coverage_percentage: Annotated[float, Field(ge=0, le=100)]
    # Reproduction
    reproduction_status: WorkflowReproductionStatus
    reproduction_checks_complete: bool
    reproduction_evidence_ids: list[str]
    reproduction_blockers: list[str]
    reproduction_explanation: str
    # Reasoning decision/output
    reasoning_allowed: bool
    reasoning_mode: WorkflowReasoningMode
    reasoning_blockers: list[str]
    reasoning_warnings: list[str]
    reasoning_decision_reason: str
    provider_call_required: bool
    reasoning_result: dict[str, Any] | None
    llm_invocation_ids: list[str]
    llm_skip_reason: str
    evidence_gate_decision: dict[str, Any]
    ai_reasoning_invoked: bool
    reasoning_validation_errors: list[str]
    reasoning_claim_validations: list[dict[str, Any]]
    reasoning_persisted: bool
    llm_audit_complete: bool
    reasoning_provider: str
    reasoning_model: str
    prompt_hash: str
    prompt_evidence_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    deterministic_fallback_reason: str
    # Reporting
    structured_report: dict[str, Any] | None
    report_validation_errors: list[str]
    report_artifact_ids: list[str]
    quality_review_required: bool
    # Diagnostics
    errors: list[ErrorRecord]
    warnings: list[str]


_STATE_ADAPTER = TypeAdapter(InvestigationState)


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def create_initial_investigation_state(
    *,
    investigation_id: str,
    workspace_id: str,
    question: str,
    actor_id: str = "",
    correlation_id: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    deadline_at: datetime | None = None,
    environment: str = "",
    environment_policy: EnvironmentPolicyRecord | None = None,
    requested_database: str = "",
    requested_entity: str = "",
    requested_objects: list[str] | None = None,
    investigation_intent: InvestigationIntent = InvestigationIntent.UNKNOWN,
) -> InvestigationState:
    """Create deterministic, side-effect-free state with isolated mutable collections."""
    resolved_id = _required_text(investigation_id, "investigation_id")
    resolved_workspace = _required_text(workspace_id, "workspace_id")
    resolved_question = _required_text(question, "question")
    now = created_at or datetime.now(UTC)
    start = started_at or now
    state: InvestigationState = {
        "investigation_id": resolved_id,
        "workspace_id": resolved_workspace,
        "actor_id": actor_id.strip(),
        "correlation_id": correlation_id if correlation_id is not None else resolved_id,
        "created_at": now,
        "updated_at": now,
        "question": resolved_question,
        "environment": environment,
        "environment_policy": environment_policy or EnvironmentPolicyRecord(),
        "requested_database": requested_database,
        "requested_entity": requested_entity,
        "requested_objects": list(requested_objects or []),
        "investigation_intent": investigation_intent,
        "current_node": "",
        "previous_node": "",
        "workflow_iteration": 0,
        "planning_round": 0,
        "query_count": 0,
        "object_count": 0,
        "started_at": start,
        "deadline_at": deadline_at,
        "cancel_requested": False,
        "stop_reason": "",
        "terminal_status": WorkflowTerminalStatus.RUNNING,
        "entity_resolution_status": EntityResolutionStatus.NOT_STARTED,
        "resolved_entities": [],
        "entity_candidates": [],
        "entity_resolution_method": "",
        "entity_resolution_explanation": "",
        "entity_ambiguities": [],
        "candidate_objects": [],
        "ranked_candidates": [],
        "active_candidate_id": "",
        "backtrack_count": 0,
        "expansion_count": 0,
        "graph_step_count": 0,
        "max_backtracks": 4,
        "max_expansions": 3,
        "max_candidate_tables": 8,
        "max_candidate_columns": 24,
        "max_candidate_code_objects": 20,
        "max_graph_steps": 50,
        "candidate_transition_trace": [],
        "selected_objects": [],
        "required_objects": [],
        "optional_objects": [],
        "relationship_edges": [],
        "metadata_gaps": [],
        "investigation_plan": [],
        "completed_plan_steps": [],
        "failed_plan_steps": [],
        "skipped_plan_steps": [],
        "proposed_queries": [],
        "approved_queries": [],
        "rejected_queries": [],
        "query_results": [],
        "plan_fingerprints": [],
        "rejected_query_hashes": [],
        "no_progress_rounds": 0,
        "replan_reason": "",
        "max_planning_rounds": 3,
        "max_queries": 10,
        "max_objects": 20,
        "no_progress_limit": 1,
        "evidence_ids": [],
        "verified_evidence_ids": [],
        "unverified_evidence_ids": [],
        "evidence_gaps": [],
        "claim_evidence_links": [],
        "findings": [],
        "coverage_status": CoverageStatus.NOT_STARTED,
        "inspected_objects": [],
        "successful_objects": [],
        "failed_objects": [],
        "skipped_objects": [],
        "inaccessible_objects": [],
        "missing_required_objects": [],
        "coverage_percentage": 0.0,
        "reproduction_status": WorkflowReproductionStatus.NOT_ASSESSED,
        "reproduction_checks_complete": False,
        "reproduction_evidence_ids": [],
        "reproduction_blockers": [],
        "reproduction_explanation": "",
        "reasoning_allowed": False,
        "reasoning_mode": WorkflowReasoningMode.NOT_DECIDED,
        "reasoning_blockers": [],
        "reasoning_warnings": [],
        "reasoning_decision_reason": "",
        "provider_call_required": False,
        "reasoning_result": None,
        "llm_invocation_ids": [],
        "llm_skip_reason": "",
        "evidence_gate_decision": {},
        "ai_reasoning_invoked": False,
        "reasoning_validation_errors": [],
        "reasoning_claim_validations": [],
        "reasoning_persisted": False,
        "llm_audit_complete": False,
        "reasoning_provider": "",
        "reasoning_model": "",
        "prompt_hash": "",
        "prompt_evidence_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost": 0.0,
        "deterministic_fallback_reason": "",
        "structured_report": None,
        "report_validation_errors": [],
        "report_artifact_ids": [],
        "quality_review_required": False,
        "errors": [],
        "warnings": [],
    }
    return _STATE_ADAPTER.validate_python(state)


def append_evidence_reference(
    state: InvestigationState,
    evidence_id: str,
    *,
    verified: bool,
) -> None:
    """Append one unique reference; verified evidence is never silently downgraded."""
    reference = _required_text(evidence_id, "evidence_id")
    if reference not in state["evidence_ids"]:
        state["evidence_ids"].append(reference)
    if verified:
        if reference not in state["verified_evidence_ids"]:
            state["verified_evidence_ids"].append(reference)
        if reference in state["unverified_evidence_ids"]:
            state["unverified_evidence_ids"].remove(reference)
    elif (
        reference not in state["verified_evidence_ids"]
        and reference not in state["unverified_evidence_ids"]
    ):
        state["unverified_evidence_ids"].append(reference)


def calculate_coverage(state: InvestigationState) -> None:
    """Calculate coverage from required objects only; optional objects do not affect it."""
    required = list(dict.fromkeys(item.qualified_name for item in state["required_objects"]))
    successful = set(state["successful_objects"])
    inaccessible = set(state["inaccessible_objects"])
    completed = [name for name in required if name in successful]
    missing = [name for name in required if name not in successful]
    state["missing_required_objects"] = missing
    state["coverage_percentage"] = 100.0 * len(completed) / len(required) if required else 0.0
    if not required:
        state["coverage_status"] = CoverageStatus.NOT_STARTED
    elif not missing:
        state["coverage_status"] = CoverageStatus.COMPLETE
    elif inaccessible & set(missing) and not completed:
        state["coverage_status"] = CoverageStatus.BLOCKED
    else:
        state["coverage_status"] = CoverageStatus.PARTIAL


def serialize_investigation_state(state: InvestigationState) -> str:
    return _STATE_ADAPTER.dump_json(state).decode("utf-8")


def deserialize_investigation_state(payload: str | bytes) -> InvestigationState:
    return _STATE_ADAPTER.validate_json(payload)


# Future graph nodes must return only updated fields. Evidence references are append-only,
# completed plan steps and terminal statuses require explicit permitted transitions, counters
# cannot be negative, exceptions become sanitized ErrorRecord values, and large SQL result sets
# remain in persistence behind evidence IDs.
