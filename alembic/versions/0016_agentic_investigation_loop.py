"""Persist multi-step agentic investigation iterations."""

import sqlalchemy as sa

from alembic import op

revision = "0016_agentic_loop"
down_revision = "0015_safe_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_agentic_steps",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("iteration_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("action_fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "evidence_request_json", sa.Text(), nullable=False, server_default=sa.text("('{}')")
        ),
        sa.Column(
            "planned_queries_json", sa.Text(), nullable=False, server_default=sa.text("('[]')")
        ),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default=sa.text("('[]')")),
        sa.Column("gap_analysis_json", sa.Text(), nullable=False, server_default=sa.text("('{}')")),
        sa.Column("budget_json", sa.Text(), nullable=False, server_default=sa.text("('{}')")),
        sa.Column("outcome", sa.String(60), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "investigation_id",
            "iteration_number",
            name="uq_investigation_agentic_step_iteration",
        ),
    )
    for column in (
        "organization_id",
        "workspace_id",
        "investigation_id",
        "state",
        "outcome",
    ):
        op.create_index(
            f"ix_investigation_agentic_steps_{column}",
            "investigation_agentic_steps",
            [column],
        )


def downgrade() -> None:
    for column in (
        "outcome",
        "state",
        "investigation_id",
        "workspace_id",
        "organization_id",
    ):
        op.drop_index(
            f"ix_investigation_agentic_steps_{column}",
            table_name="investigation_agentic_steps",
        )
    op.drop_table("investigation_agentic_steps")
