"""Add governed LLM model catalog, policy, entitlements, and selection audit.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "llm_model_catalog",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_model_id", sa.String(160), nullable=False),
        sa.Column("model_category", sa.String(40), nullable=False, server_default="custom"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "default_reasoning_effort", sa.String(40), nullable=False, server_default="medium"
        ),
        sa.Column("maximum_reasoning_effort", sa.String(40), nullable=False, server_default="high"),
        sa.Column("context_limit", sa.Integer()),
        sa.Column("cost_tier", sa.String(40), nullable=False, server_default="standard"),
        sa.Column("latency_tier", sa.String(40), nullable=False, server_default="standard"),
        sa.Column("recommended_usage", sa.Text(), nullable=False, server_default=""),
        sa.Column("availability_status", sa.String(40), nullable=False, server_default="available"),
        sa.Column("retirement_date", sa.DateTime(timezone=True)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("premium", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("automatic_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("configuration_version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.UniqueConstraint(
            "organization_id", "provider", "provider_model_id", name="uq_llm_catalog_provider_model"
        ),
    )
    op.create_index("ix_llm_model_catalog_org", "llm_model_catalog", ["organization_id"])

    op.create_table(
        "llm_model_policy",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "user_selection_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "automatic_mode_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "admin_management_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "global_default_model_id",
            sa.String(36),
            sa.ForeignKey("llm_model_catalog.id", ondelete="SET NULL"),
        ),
        sa.Column("automatic_candidate_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "fallback_model_id",
            sa.String(36),
            sa.ForeignKey("llm_model_catalog.id", ondelete="SET NULL"),
        ),
        sa.Column("fallback_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "require_premium_approval", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("allowed_environments_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("selection_roles_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cost_ceiling_tier", sa.String(40), nullable=False, server_default="premium"),
        sa.Column("latency_preference", sa.String(40), nullable=False, server_default="balanced"),
        sa.Column("configuration_version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
    )

    for table, subject, subject_fk, unique_name in (
        ("llm_model_role_entitlement", "role", None, "uq_llm_role_entitlement"),
        ("llm_model_user_entitlement", "user_id", "users.id", "uq_llm_user_entitlement"),
        (
            "llm_model_workspace_entitlement",
            "workspace_id",
            "workspaces.id",
            "uq_llm_workspace_entitlement",
        ),
    ):
        subject_column = (
            sa.Column(subject, sa.String(80), nullable=False)
            if subject_fk is None
            else sa.Column(
                subject,
                sa.String(36),
                sa.ForeignKey(subject_fk, ondelete="CASCADE"),
                nullable=False,
            )
        )
        extras = []
        if table == "llm_model_user_entitlement":
            extras = [
                sa.Column(
                    "approved_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")
                ),
                sa.Column("approval_starts_at", sa.DateTime(timezone=True)),
                sa.Column("approval_expires_at", sa.DateTime(timezone=True)),
            ]
        op.create_table(
            table,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "model_id",
                sa.String(36),
                sa.ForeignKey("llm_model_catalog.id", ondelete="CASCADE"),
                nullable=False,
            ),
            subject_column,
            sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
            *extras,
            *_timestamps(),
            sa.UniqueConstraint("organization_id", "model_id", subject, name=unique_name),
        )

    op.create_table(
        "llm_model_selection_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("investigation_id", sa.String(36)),
        sa.Column("requested_mode", sa.String(40), nullable=False, server_default=""),
        sa.Column("requested_catalog_model_id", sa.String(36)),
        sa.Column("effective_catalog_model_id", sa.String(36)),
        sa.Column("effective_provider", sa.String(80), nullable=False, server_default=""),
        sa.Column("effective_provider_model_id", sa.String(160), nullable=False, server_default=""),
        sa.Column("reasoning_effort", sa.String(40), nullable=False, server_default=""),
        sa.Column("selection_source", sa.String(40), nullable=False),
        sa.Column("policy_decision", sa.String(40), nullable=False),
        sa.Column("policy_decision_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("entitlement_source", sa.String(120), nullable=False, server_default=""),
        sa.Column("fallback_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("candidate_model_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("routing_factors_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("model_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("configuration_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_llm_model_selection_audit_requested", "llm_model_selection_audit", ["requested_at"]
    )
    op.create_index(
        "ix_llm_model_selection_audit_investigation",
        "llm_model_selection_audit",
        ["investigation_id"],
    )

    investigation_columns = (
        sa.Column("requested_model_mode", sa.String(40), nullable=False, server_default=""),
        sa.Column("requested_catalog_model_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("effective_catalog_model_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("model_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("model_policy_decision", sa.String(40), nullable=False, server_default=""),
        sa.Column("model_policy_decision_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("model_entitlement_source", sa.String(120), nullable=False, server_default=""),
        sa.Column("model_selection_source", sa.String(40), nullable=False, server_default=""),
        sa.Column("model_selection_requested_at", sa.DateTime(timezone=True)),
        sa.Column(
            "model_selection_configuration_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    for column in investigation_columns:
        op.add_column("investigations", column)


def downgrade() -> None:
    for column in (
        "model_selection_configuration_version",
        "model_selection_requested_at",
        "model_selection_source",
        "model_entitlement_source",
        "model_policy_decision_reason",
        "model_policy_decision",
        "model_snapshot_json",
        "effective_catalog_model_id",
        "requested_catalog_model_id",
        "requested_model_mode",
    ):
        op.drop_column("investigations", column)
    op.drop_index(
        "ix_llm_model_selection_audit_investigation", table_name="llm_model_selection_audit"
    )
    op.drop_index("ix_llm_model_selection_audit_requested", table_name="llm_model_selection_audit")
    op.drop_table("llm_model_selection_audit")
    op.drop_table("llm_model_workspace_entitlement")
    op.drop_table("llm_model_user_entitlement")
    op.drop_table("llm_model_role_entitlement")
    op.drop_table("llm_model_policy")
    op.drop_index("ix_llm_model_catalog_org", table_name="llm_model_catalog")
    op.drop_table("llm_model_catalog")
