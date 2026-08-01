"""Persist investigation execution metadata.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = (
        sa.Column("workflow_engine", sa.String(40), nullable=False, server_default="Legacy"),
        sa.Column("execution_mode", sa.String(40), nullable=False, server_default="LEGACY"),
        sa.Column("graph_version", sa.String(80), nullable=False, server_default=""),
        sa.Column("graph_execution_id", sa.String(120), nullable=False, server_default=""),
        sa.Column("requested_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("effective_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("execution_provider", sa.String(80), nullable=False, server_default=""),
        sa.Column("reasoning_effort", sa.String(40), nullable=False, server_default=""),
        sa.Column("selected_by", sa.String(40), nullable=False, server_default="Automatic"),
        sa.Column("execution_policy_version", sa.String(40), nullable=False, server_default=""),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fallback_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in columns:
        op.add_column("investigations", column)
    op.create_index(
        "ix_investigations_graph_execution_id",
        "investigations",
        ["graph_execution_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_investigations_graph_execution_id", table_name="investigations")
    for name in (
        "execution_ended_at",
        "execution_started_at",
        "fallback_reason",
        "fallback_used",
        "execution_policy_version",
        "selected_by",
        "reasoning_effort",
        "execution_provider",
        "effective_model",
        "requested_model",
        "graph_execution_id",
        "graph_version",
        "execution_mode",
        "workflow_engine",
    ):
        op.drop_column("investigations", name)
