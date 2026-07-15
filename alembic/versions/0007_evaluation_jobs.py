"""Add durable tenant-scoped evaluation jobs."""

from alembic import op
from legacydb_copilot.db.models import EvaluationJobModel

revision = "0007_evaluation_jobs"
down_revision = "0006_ai_judge_human_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    EvaluationJobModel.__table__.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    EvaluationJobModel.__table__.drop(op.get_bind(), checkfirst=False)
