from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from legacydb_copilot.auth import Role
from legacydb_copilot.billing import Plan
from legacydb_copilot.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from legacydb_copilot.incidents import IncidentStatus


class OrganizationModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["UserModel"]] = relationship(back_populates="organization")
    workspaces: Mapped[list["WorkspaceModel"]] = relationship(back_populates="organization")


class UserModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    role: Mapped[str] = mapped_column(String(60), default=Role.READ_ONLY.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[object | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped["OrganizationModel"] = relationship(back_populates="users")
    consents: Mapped[list["ConsentModel"]] = relationship(back_populates="user")
    workspace_memberships: Mapped[list["WorkspaceMembershipModel"]] = relationship(
        back_populates="user"
    )

    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_user_org_email"),)


class ConsentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_consents"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    consent_key: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(80), nullable=False)
    accepted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["UserModel"] = relationship(back_populates="consents")

    __table_args__ = (UniqueConstraint("user_id", "consent_key", name="uq_user_consent_key"),)


class WorkspaceModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["OrganizationModel"] = relationship(back_populates="workspaces")
    database_connections: Mapped[list["DatabaseConnectionModel"]] = relationship(
        back_populates="workspace"
    )
    documents: Mapped[list["DocumentModel"]] = relationship(back_populates="workspace")
    incidents: Mapped[list["IncidentModel"]] = relationship(back_populates="workspace")
    investigations: Mapped[list["InvestigationModel"]] = relationship(back_populates="workspace")
    memberships: Mapped[list["WorkspaceMembershipModel"]] = relationship(
        back_populates="workspace"
    )

    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_workspace_org_slug"),)


class WorkspaceMembershipModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_memberships"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspace: Mapped["WorkspaceModel"] = relationship(back_populates="memberships")
    user: Mapped["UserModel"] = relationship(back_populates="workspace_memberships")

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_user"),
        Index("ix_workspace_memberships_user_active", "user_id", "is_active"),
    )


class DatabaseConnectionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "database_connections"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    engine: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    host: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    port: Mapped[int | None] = mapped_column(Integer)
    database_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped["WorkspaceModel"] = relationship(back_populates="database_connections")

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_database_connection_workspace_name"),
    )


class DocumentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    workspace: Mapped["WorkspaceModel"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersionModel"]] = relationship(back_populates="document")


class DocumentVersionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False)
    indexed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))

    document: Mapped["DocumentModel"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_version_number"),
        CheckConstraint("size_bytes > 0", name="ck_document_version_size_positive"),
    )


class KnowledgeChunkModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(80), default="document", nullable=False, index=True)
    source_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    module_name: Mapped[str] = mapped_column(String(120), default="", nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(120), default="", nullable=False, index=True)
    procedure_name: Mapped[str] = mapped_column(String(120), default="", nullable=False, index=True)
    business_object: Mapped[str] = mapped_column(String(120), default="", nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(120), default="", nullable=False, index=True)
    tags: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(60), default="uploaded", nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))

    __table_args__ = (
        Index("ix_knowledge_chunks_workspace_source", "workspace_id", "source"),
        Index("ix_knowledge_chunks_workspace_approval", "workspace_id", "approval_status"),
    )


class IncidentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incidents"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(60),
        default=IncidentStatus.OPEN.value,
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)

    workspace: Mapped["WorkspaceModel"] = relationship(back_populates="incidents")
    knowledge_articles: Mapped[list["KnowledgeArticleModel"]] = relationship(
        back_populates="incident"
    )


class InvestigationModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigations"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[str] = mapped_column(String, default="", nullable=False, index=True)
    connection_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    user_question: Mapped[str] = mapped_column(Text, nullable=False)
    detected_intent: Mapped[str] = mapped_column(String(80), default="UNKNOWN", nullable=False, index=True)
    extracted_entities_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    sql_queries_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    ai_answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    report_path: Mapped[str] = mapped_column(String(700), default="", nullable=False)
    report_storage_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    report_snapshot_json: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ai_debug_trace_json: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(60), default="AI_ANSWERED", nullable=False, index=True)

    workspace: Mapped["WorkspaceModel"] = relationship(back_populates="investigations")
    feedback_items: Mapped[list["InvestigationFeedbackModel"]] = relationship(
        back_populates="investigation"
    )
    verification_checks: Mapped[list["VerificationCheckModel"]] = relationship(
        back_populates="investigation"
    )


class VerificationCheckModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Owner: Mukesh Dabi
    Purpose:
        Stores human-approved verification checks suggested after an investigation.
    Input:
        Claims, read-only SQL, explanation text, and execution result metadata.
    Output:
        Persisted verification workflow records returned to the UI and reports.
    Called by:
        /chat/ask when creating suggested checks, and verification endpoints when users run/skip checks.
    Flow:
        Investigation report -> Suggested checks -> User approval -> Safe SQL execution -> Report regeneration.
    Safety:
        Records suggested SQL only; execution still goes through SafeSQLValidator and never runs writes or procedures.
    """

    __tablename__ = "verification_checks"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    claim_being_verified: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_logic: Mapped[str] = mapped_column(Text, default="", nullable=False)
    expected_result_explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    interpretation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    conclusion_template: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verification_sql: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risk_level: Mapped[str] = mapped_column(String(60), default="Read-only", nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="SQL evidence", nullable=False)
    status: Mapped[str] = mapped_column(String(60), default="Pending", nullable=False, index=True)
    actual_result_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence_impact: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verified_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    verified_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    verified_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))

    investigation: Mapped["InvestigationModel"] = relationship(back_populates="verification_checks")


class InvestigationFeedbackModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigation_feedback"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    rating: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    actual_root_cause: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actual_fix_applied: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sql_or_procedure_changed: Mapped[str] = mapped_column(Text, default="", nullable=False)
    test_cases_executed: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proof_of_fix: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rollback_used: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    production_issue_resolved: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(60), default="PENDING_APPROVAL", nullable=False, index=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    investigation: Mapped["InvestigationModel"] = relationship(back_populates="feedback_items")


class KnowledgeArticleModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_articles"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    approved_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    module_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    issue_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    symptoms: Mapped[str] = mapped_column(Text, default="", nullable=False)
    detected_entities: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    actual_root_cause: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fix_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sql_changed: Mapped[str] = mapped_column(Text, default="", nullable=False)
    procedures_changed: Mapped[str] = mapped_column(Text, default="", nullable=False)
    test_cases: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proof_of_fix: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rollback_plan: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    confidence_after_approval: Mapped[float | None] = mapped_column(Numeric(5, 4))
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    source_investigation_id: Mapped[str | None] = mapped_column(
        ForeignKey("investigations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    indexed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))

    incident: Mapped["IncidentModel"] = relationship(back_populates="knowledge_articles")


class ChatConversationModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_conversations"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New conversation", nullable=False)

    messages: Mapped[list["ChatMessageModel"]] = relationship(back_populates="conversation")


class ChatMessageModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    conversation: Mapped["ChatConversationModel"] = relationship(back_populates="messages")


class AuditLogModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="success", nullable=False, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    occurred_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


class SubscriptionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan: Mapped[str] = mapped_column(String(40), default=Plan.FREE.value, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="stripe", nullable=False)
    provider_customer_id: Mapped[str | None] = mapped_column(String(255))
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    in_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grace_period_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PaymentEventModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_events"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    amount: Mapped[object | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(12), default="usd", nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


Index("ix_documents_tenant_workspace_deleted", DocumentModel.organization_id, DocumentModel.workspace_id, DocumentModel.is_deleted)
Index("ix_incidents_tenant_workspace_status", IncidentModel.organization_id, IncidentModel.workspace_id, IncidentModel.status)
Index("ix_investigations_tenant_workspace_status", InvestigationModel.organization_id, InvestigationModel.workspace_id, InvestigationModel.status)
Index("ix_feedback_tenant_workspace_status", InvestigationFeedbackModel.organization_id, InvestigationFeedbackModel.workspace_id, InvestigationFeedbackModel.status)
Index("ix_knowledge_tenant_workspace_active", KnowledgeArticleModel.organization_id, KnowledgeArticleModel.workspace_id, KnowledgeArticleModel.is_active)
Index("ix_chat_messages_conversation_created", ChatMessageModel.conversation_id, ChatMessageModel.created_at)
Index("ix_audit_logs_tenant_workspace_action", AuditLogModel.organization_id, AuditLogModel.workspace_id, AuditLogModel.action)
