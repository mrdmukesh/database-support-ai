"""Persist Safe Investigation Planner selections."""

import sqlalchemy as sa

from alembic import op

revision = "0015_safe_planner"
down_revision = "0014_evidence_gaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_planner_selections",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("action_fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "evidence_request_json", sa.Text(), nullable=False, server_default=sa.text("('{}')")
        ),
        sa.Column("selection_reason", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("expected_information_gain", sa.Numeric(5, 4), nullable=False),
        sa.Column("retry_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "ranking_audit_json", sa.Text(), nullable=False, server_default=sa.text("('[]')")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "workspace_id",
        "investigation_id",
        "status",
        "action_fingerprint",
    ):
        op.create_index(
            f"ix_investigation_planner_selections_{column}",
            "investigation_planner_selections",
            [column],
        )


def downgrade() -> None:
    for column in (
        "action_fingerprint",
        "status",
        "investigation_id",
        "workspace_id",
        "organization_id",
    ):
        op.drop_index(
            f"ix_investigation_planner_selections_{column}",
            table_name="investigation_planner_selections",
        )
    op.drop_table("investigation_planner_selections")
