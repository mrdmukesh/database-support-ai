"""Persist investigation LLM outcomes and provider request identifiers."""

from alembic import op
import sqlalchemy as sa

revision = "0009_llm_audit_outcomes"
down_revision = "0008_llm_invocation_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column("llm_audit_outcome", sa.String(80), nullable=False, server_default=""))
    op.add_column("investigations", sa.Column("llm_audit_reason", sa.Text(), nullable=False, server_default=""))
    op.create_index("ix_investigations_llm_audit_outcome", "investigations", ["llm_audit_outcome"])
    op.add_column("llm_invocation_audit", sa.Column("provider_request_id", sa.String(160), nullable=True))
    op.create_index("ix_llm_invocation_audit_provider_request_id", "llm_invocation_audit", ["provider_request_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_invocation_audit_provider_request_id", table_name="llm_invocation_audit")
    op.drop_column("llm_invocation_audit", "provider_request_id")
    op.drop_index("ix_investigations_llm_audit_outcome", table_name="investigations")
    op.drop_column("investigations", "llm_audit_reason")
    op.drop_column("investigations", "llm_audit_outcome")
