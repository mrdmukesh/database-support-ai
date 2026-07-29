"""Persist root-cause hypothesis verification matrices."""

import sqlalchemy as sa

from alembic import op

revision = "0018_hypothesis_verify"
down_revision = "0017_execution_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "root_cause_hypothesis_verifications",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("hypothesis_id", sa.String(120), nullable=False),
        sa.Column("origin", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("hypothesis_json", sa.Text(), nullable=False),
        sa.Column("verification_matrix_json", sa.Text(), nullable=False),
        sa.Column(
            "valid_evidence_refs_json", sa.Text(), nullable=False, server_default=sa.text("('[]')")
        ),
        sa.Column(
            "missing_proof_json", sa.Text(), nullable=False, server_default=sa.text("('[]')")
        ),
        sa.Column(
            "contradictions_json", sa.Text(), nullable=False, server_default=sa.text("('[]')")
        ),
        sa.Column("evidence_package_hash", sa.String(64), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("visible_in_report", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        "origin",
        "status",
        "evidence_package_hash",
    ):
        op.create_index(
            f"ix_root_cause_hypothesis_verifications_{column}",
            "root_cause_hypothesis_verifications",
            [column],
        )


def downgrade() -> None:
    for column in (
        "evidence_package_hash",
        "status",
        "origin",
        "investigation_id",
        "workspace_id",
        "organization_id",
    ):
        op.drop_index(
            f"ix_root_cause_hypothesis_verifications_{column}",
            table_name="root_cause_hypothesis_verifications",
        )
    op.drop_table("root_cause_hypothesis_verifications")
