"""Add immutable deterministic weighted-score records."""

from alembic import op
from evaluation.framework.models import EvaluationDeterministicScoreModel

revision = "0005_deterministic_scoring"
down_revision = "0004_evaluation_runner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    EvaluationDeterministicScoreModel.__table__.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    EvaluationDeterministicScoreModel.__table__.drop(op.get_bind(), checkfirst=False)
