"""Add durable tenant-scoped evaluation jobs."""

from alembic import op
from legacydb_copilot.db.models import EvaluationJobModel

revision = "0007_evaluation_jobs"
down_revision = "0006_ai_judge_human_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Application startup may run Base.metadata.create_all before Alembic in
    # existing installations. Preserve that table and let Alembic adopt the
    # matching model instead of failing while advancing from revision 0006.
    EvaluationJobModel.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    EvaluationJobModel.__table__.drop(op.get_bind(), checkfirst=True)
