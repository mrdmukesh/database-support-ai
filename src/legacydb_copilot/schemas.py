from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from legacydb_copilot.auth import Role
from legacydb_copilot.billing import Plan
from legacydb_copilot.incidents import IncidentStatus


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    is_active: bool


class UserCreate(BaseModel):
    organization_id: str
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1)
    full_name: str = ""
    role: Role = Role.READ_ONLY
    consents: set[str]
    ip_address: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    email: str
    full_name: str
    role: str
    is_active: bool


class AdminUserCreate(BaseModel):
    organization_id: str
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(default="", max_length=200)
    role: Role = Role.READ_ONLY


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    role: Role | None = None
    is_active: bool | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"
    user: UserRead


class EvaluationServiceTokenRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=200)
    client_secret: str = Field(min_length=1, max_length=512)


class EvaluationServiceTokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class WorkspaceCreate(BaseModel):
    organization_id: str
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    is_active: bool | None = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    slug: str
    is_active: bool


class WorkspaceMembershipUpsert(BaseModel):
    user_id: str
    role: str = Field(pattern=r"^(OWNER|ADMIN|DBA|DEVELOPER|VIEWER|AUDITOR)$")


class WorkspaceMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    workspace_id: str
    user_id: str
    role: str
    is_active: bool


class DatabaseConnectionCreate(BaseModel):
    organization_id: str
    workspace_id: str
    engine: str
    name: str
    host: str = ""
    port: int | None = None
    database_name: str = ""
    secret_ref: str = ""
    connection_string: str | None = None
    environment_type: str = Field(
        pattern=r"^(production|uat|test|development|evaluation|demo)$",
    )
    max_scan_rows: int | None = Field(default=None, ge=1, le=5000)

    @model_validator(mode="after")
    def default_scan_rows_for_environment(self):
        if self.max_scan_rows is None:
            self.max_scan_rows = 500 if self.environment_type == "uat" else 1000 if self.environment_type in {"test", "evaluation", "demo"} else 100
        return self


class DatabaseConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    connection_string: str | None = None
    is_active: bool | None = None
    environment_type: str | None = Field(
        default=None,
        pattern=r"^(production|uat|test|evaluation|demo)$",
    )
    max_scan_rows: int | None = Field(default=None, ge=1, le=5000)


class DatabaseConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    workspace_id: str
    engine: str
    name: str
    database_name: str
    environment_type: str
    max_scan_rows: int
    is_active: bool


class DocumentCreate(BaseModel):
    organization_id: str
    workspace_id: str
    owner_id: str
    title: str
    filename: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)
    storage_key: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    workspace_id: str
    title: str
    current_version: int


class IncidentCreate(BaseModel):
    organization_id: str
    workspace_id: str
    created_by_id: str
    title: str
    description: str = ""
    severity: str = "medium"


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    workspace_id: str
    title: str
    status: str
    severity: str


class IncidentTransition(BaseModel):
    status: IncidentStatus


class SubscriptionUpsert(BaseModel):
    organization_id: str
    plan: Plan
    provider: str = "stripe"
    active: bool = True
    in_trial: bool = False
    grace_period_days: int = Field(default=0, ge=0)


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    plan: str
    provider: str
    active: bool
    in_trial: bool
    grace_period_days: int


class ChatAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str
    workspace_id: str
    connection_id: str | None = None
    environment_type: str | None = None
    user_id: str
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    model_selection_mode: str | None = Field(default=None, max_length=40)
    catalog_model_id: str | None = Field(default=None, max_length=36)


class ModelCatalogCreate(BaseModel):
    organization_id: str
    display_name: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=80)
    provider_model_id: str = Field(min_length=1, max_length=160)
    model_category: str = Field(default="custom", pattern=r"^(fast|deep_analysis|custom)$")
    description: str = Field(default="", max_length=2000)
    enabled: bool = True
    default_reasoning_effort: str = "medium"
    maximum_reasoning_effort: str = "high"
    context_limit: int | None = Field(default=None, ge=1)
    cost_tier: str = "standard"
    latency_tier: str = "standard"
    recommended_usage: str = Field(default="", max_length=2000)
    availability_status: str = "available"
    retirement_date: datetime | None = None
    sort_order: int = 100
    premium: bool = False
    automatic_eligible: bool = False


class ModelCatalogUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    provider: str | None = Field(default=None, min_length=1, max_length=80)
    provider_model_id: str | None = Field(default=None, min_length=1, max_length=160)
    model_category: str | None = Field(default=None, pattern=r"^(fast|deep_analysis|custom)$")
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None
    default_reasoning_effort: str | None = None
    maximum_reasoning_effort: str | None = None
    context_limit: int | None = Field(default=None, ge=1)
    cost_tier: str | None = None
    latency_tier: str | None = None
    recommended_usage: str | None = Field(default=None, max_length=2000)
    availability_status: str | None = None
    retirement_date: datetime | None = None
    sort_order: int | None = None
    premium: bool | None = None
    automatic_eligible: bool | None = None


class ModelCatalogRead(ModelCatalogCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    configuration_version: int
    created_at: datetime
    updated_at: datetime


class ModelPolicyUpdate(BaseModel):
    user_selection_enabled: bool | None = None
    automatic_mode_enabled: bool | None = None
    admin_management_enabled: bool | None = None
    global_default_model_id: str | None = None
    automatic_candidate_ids: list[str] | None = None
    fallback_model_id: str | None = None
    fallback_enabled: bool | None = None
    require_premium_approval: bool | None = None
    allowed_environments: list[str] | None = None
    selection_roles: list[str] | None = None
    cost_ceiling_tier: str | None = None
    latency_preference: str | None = None


class ModelEntitlementUpdate(BaseModel):
    model_id: str
    allowed: bool = True
    approval_starts_at: datetime | None = None
    approval_expires_at: datetime | None = None


class UserModelAccessUpdate(BaseModel):
    organization_id: str
    entitlements: list[ModelEntitlementUpdate]


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    confidence: float | None
    source_count: int
    requires_human_review: bool


class ChatConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    workspace_id: str
    user_id: str
    title: str


class ExecutionMetadataRead(BaseModel):
    workflow_engine: str = "LangGraph"
    execution_mode: str = "LANGGRAPH"
    graph_version: str = ""
    graph_execution_id: str = ""
    requested_model: str = ""
    effective_model: str = ""
    provider: str = ""
    reasoning_effort: str = ""
    selected_by: str = "Automatic"
    policy_version: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""
    requested_model_mode: str = ""
    requested_catalog_model_id: str = ""
    effective_catalog_model_id: str = ""
    model_policy_decision: str = ""
    model_policy_decision_reason: str = ""
    model_entitlement_source: str = ""
    model_selection_configuration_version: int = 0
    execution_started_at: datetime | None = None
    execution_ended_at: datetime | None = None
    badge: str = "LangGraph Verified"


class ChatAskResponse(BaseModel):
    conversation: ChatConversationRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    findings: list[str]
    confidence: float
    requires_human_review: bool
    sources: list[str]
    report: dict[str, str] | None = None
    investigation_id: str | None = None
    connection_id: str
    connection_name: str
    environment_type: str
    policy_name: str
    policy_version: str
    safety_profile: str
    environment_source: str
    execution_metadata: ExecutionMetadataRead


class VerificationCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    claim: str
    purpose: str = ""
    claim_being_verified: str = ""
    evidence_logic: str = ""
    expected_result_explanation: str = ""
    interpretation: str = ""
    conclusion_template: str = ""
    verification_sql: str
    expected_result: str
    risk_level: str
    source: str
    status: str
    actual_result_summary: str
    confidence_impact: str
    notes: str
    verified_by: str
    verified_at: datetime | None


class VerificationRunRequest(BaseModel):
    verification_sql: str | None = None


class VerificationRunAllResponse(BaseModel):
    checks: list[VerificationCheckRead]
    report: dict[str, str] | None = None


class InvestigationStatus(StrEnum):
    OPEN = "OPEN"
    AI_ANSWERED = "AI_ANSWERED"
    DEVELOPER_REVIEW = "DEVELOPER_REVIEW"
    FIX_APPLIED = "FIX_APPLIED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED_KNOWLEDGE = "APPROVED_KNOWLEDGE"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class FeedbackRating(StrEnum):
    HELPFUL = "HELPFUL"
    NOT_HELPFUL = "NOT_HELPFUL"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    WRONG_ROOT_CAUSE = "WRONG_ROOT_CAUSE"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    NEEDS_DBA_REVIEW = "NEEDS_DBA_REVIEW"


class InvestigationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    workspace_id: str
    connection_id: str
    connection_name: str
    selected_database_name: str
    environment_type: str
    policy_name: str
    safety_profile: str
    environment_source: str
    environment_snapshot_json: str
    environment_telemetry_json: str
    policy_version: str
    policy_audit_json: str
    workflow_engine: str = "LangGraph"
    execution_mode: str = "LANGGRAPH"
    graph_version: str = ""
    graph_execution_id: str = ""
    requested_model: str = ""
    effective_model: str = ""
    execution_provider: str = ""
    reasoning_effort: str = ""
    selected_by: str = "Automatic"
    execution_policy_version: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""
    execution_started_at: datetime | None = None
    execution_ended_at: datetime | None = None
    user_question: str
    detected_intent: str
    evidence_gap_analysis_json: str
    ai_answer: str
    confidence_score: float | None
    report_path: str
    status: str
    created_at: datetime


class InvestigationStateTransitionRead(BaseModel):
    investigation_id: str
    previous_state: str | None
    current_state: str
    transitioned_at: datetime
    reason: str
    iteration_number: int


class InvestigationStateHistoryRead(BaseModel):
    investigation_id: str
    current: InvestigationStateTransitionRead | None
    transitions: list[InvestigationStateTransitionRead]


class InvestigationAgenticStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    iteration_number: int
    state: str
    action_fingerprint: str
    evidence_request_json: str
    planned_queries_json: str
    evidence_json: str
    gap_analysis_json: str
    budget_json: str
    outcome: str
    reason: str
    duration_ms: int
    created_at: datetime


class ExecutionPathTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    affected_entity: str
    status: str
    expected_path_json: str
    nodes_json: str
    edges_json: str
    verified_completed_steps_json: str
    last_successful_step: str
    first_failed_or_missing_step: str
    responsible_component: str
    remaining_gap: str
    created_at: datetime


class FixReadinessAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    state: str
    score: int
    criteria_json: str
    blockers_json: str
    recommended_next_evidence_json: str
    confirmed_hypothesis_ids_json: str
    decision_reason: str
    created_at: datetime


class InvestigationProgressRead(BaseModel):
    investigation_id: str
    agentic: bool
    current_state: str
    iteration_number: int
    terminal: bool
    stop_reason: str
    budget: dict
    resolved_entities: list[dict]
    question_counts: dict[str, int]
    questions: list[dict]
    completed_steps: list[dict]
    failed_actions: list[dict]
    verified_absence: list[dict]
    root_cause_status: str
    fix_readiness_state: str
    source_badges: list[str]
    can_cancel: bool


class InvestigationFeedbackCreate(BaseModel):
    rating: FeedbackRating
    actual_root_cause: str = ""
    actual_fix_applied: str = ""
    sql_or_procedure_changed: str = ""
    test_cases_executed: str = ""
    proof_of_fix: str = ""
    rollback_used: str = ""
    production_issue_resolved: bool | None = None
    notes: str = ""


class InvestigationFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    workspace_id: str
    investigation_id: str
    rating: str
    actual_root_cause: str
    actual_fix_applied: str
    sql_or_procedure_changed: str
    test_cases_executed: str
    proof_of_fix: str
    rollback_used: str
    production_issue_resolved: bool | None
    notes: str
    status: str
    review_notes: str
    created_at: datetime


class FeedbackApprovalRequest(BaseModel):
    approved: bool
    review_notes: str = ""
    title: str | None = None
    module_name: str = ""
    issue_type: str = ""
    severity: str = "medium"
    rollback_plan: str = ""
    confidence_after_approval: float = Field(default=0.95, ge=0, le=1)


class KnowledgeArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    title: str
    module_name: str
    issue_type: str
    symptoms: str
    actual_root_cause: str
    fix_summary: str
    test_cases: str
    proof_of_fix: str
    severity: str
    confidence_after_approval: float | None
    source_investigation_id: str | None
    version: int
    is_active: bool
    approved_at: datetime | None


class LearningDashboardRead(BaseModel):
    open_investigations: int
    pending_feedback: int
    pending_approval: int
    approved_knowledge: int
    reminders: list[InvestigationRead]


class HelpAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    current_page: str | None = None


class HelpAskResponse(BaseModel):
    answer: str
    steps: list[str]
    related_pages: list[str]
    warnings: list[str]
    links: list[str]
