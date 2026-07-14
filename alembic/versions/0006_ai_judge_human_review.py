"""Add append-only AI judge and human-review flag records."""

from alembic import op
from evaluation.framework.models import (
    EvaluationAIJudgeScoreModel,
    EvaluationHumanReviewFlagModel,
)

revision = "0006_ai_judge_human_review"
down_revision = "0005_deterministic_scoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    EvaluationAIJudgeScoreModel.__table__.create(bind, checkfirst=False)
    EvaluationHumanReviewFlagModel.__table__.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    EvaluationHumanReviewFlagModel.__table__.drop(bind, checkfirst=False)
    EvaluationAIJudgeScoreModel.__table__.drop(bind, checkfirst=False)
