"""Persist normalized execution path traces."""

import sqlalchemy as sa

from alembic import op

revision = "0017_execution_trace"
down_revision = "0016_agentic_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_path_traces",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("affected_entity", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("expected_path_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("nodes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("edges_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "verified_completed_steps_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "last_successful_step", sa.String(120), nullable=False, server_default=""
        ),
        sa.Column(
            "first_failed_or_missing_step",
            sa.String(120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "responsible_component",
            sa.String(255),
            nullable=False,
            server_default="",
        ),
        sa.Column("remaining_gap", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"], ["investigations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "workspace_id",
        "investigation_id",
        "status",
    ):
        op.create_index(
            f"ix_execution_path_traces_{column}",
            "execution_path_traces",
            [column],
        )


def downgrade() -> None:
    for column in (
        "status",
        "investigation_id",
        "workspace_id",
        "organization_id",
    ):
        op.drop_index(
            f"ix_execution_path_traces_{column}",
            table_name="execution_path_traces",
        )
    op.drop_table("execution_path_traces")
