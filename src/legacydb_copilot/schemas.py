from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

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


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"
    user: UserRead


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


class DatabaseConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    connection_string: str | None = None
    is_active: bool | None = None


class DatabaseConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    workspace_id: str
    engine: str
    name: str
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
    organization_id: str
    workspace_id: str
    user_id: str
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


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


class VerificationCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    claim: str
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
    user_question: str
    detected_intent: str
    ai_answer: str
    confidence_score: float | None
    report_path: str
    status: str
    created_at: datetime


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
