"""Persist deterministic fix-readiness assessments."""

import sqlalchemy as sa

from alembic import op

revision = "0019_fix_readiness"
down_revision = "0018_hypothesis_verify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fix_readiness_assessments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("state", sa.String(60), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("criteria_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("blockers_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "recommended_next_evidence_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "confirmed_hypothesis_ids_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("decision_reason", sa.Text(), nullable=False, server_default=""),
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
    for column in ("organization_id", "workspace_id", "investigation_id", "state"):
        op.create_index(
            f"ix_fix_readiness_assessments_{column}",
            "fix_readiness_assessments",
            [column],
        )


def downgrade() -> None:
    for column in ("state", "investigation_id", "workspace_id", "organization_id"):
        op.drop_index(
            f"ix_fix_readiness_assessments_{column}",
            table_name="fix_readiness_assessments",
        )
    op.drop_table("fix_readiness_assessments")
