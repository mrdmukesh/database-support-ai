"""Persist investigation LLM outcomes and provider request identifiers."""

import sqlalchemy as sa

from alembic import op

revision = "0009_llm_audit_outcomes"
down_revision = "0008_llm_invocation_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    investigation_columns = {column["name"] for column in inspector.get_columns("investigations")}
    if "llm_audit_outcome" not in investigation_columns:
        op.add_column(
            "investigations",
            sa.Column(
                "llm_audit_outcome",
                sa.String(80),
                nullable=False,
                server_default="",
            ),
        )
    if "llm_audit_reason" not in investigation_columns:
        op.add_column(
            "investigations",
            sa.Column(
                "llm_audit_reason",
                sa.Text(),
                nullable=False,
                server_default=sa.text("('')"),
            ),
        )
    investigation_indexes = {index["name"] for index in inspector.get_indexes("investigations")}
    if "ix_investigations_llm_audit_outcome" not in investigation_indexes:
        op.create_index(
            "ix_investigations_llm_audit_outcome",
            "investigations",
            ["llm_audit_outcome"],
        )

    audit_columns = {column["name"] for column in inspector.get_columns("llm_invocation_audit")}
    if "provider_request_id" not in audit_columns:
        op.add_column(
            "llm_invocation_audit",
            sa.Column("provider_request_id", sa.String(160), nullable=True),
        )
    audit_indexes = {index["name"] for index in inspector.get_indexes("llm_invocation_audit")}
    if "ix_llm_invocation_audit_provider_request_id" not in audit_indexes:
        op.create_index(
            "ix_llm_invocation_audit_provider_request_id",
            "llm_invocation_audit",
            ["provider_request_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_llm_invocation_audit_provider_request_id", table_name="llm_invocation_audit")
    op.drop_column("llm_invocation_audit", "provider_request_id")
    op.drop_index("ix_investigations_llm_audit_outcome", table_name="investigations")
    op.drop_column("investigations", "llm_audit_reason")
    op.drop_column("investigations", "llm_audit_outcome")
