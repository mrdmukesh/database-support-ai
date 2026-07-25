"""Add immutable, sanitized LLM invocation audit records."""

from alembic import op
from legacydb_copilot.db.models import LLMInvocationAuditModel

revision = "0008_llm_invocation_audit"
down_revision = "0007_evaluation_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    LLMInvocationAuditModel.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    LLMInvocationAuditModel.__table__.drop(op.get_bind(), checkfirst=True)
