"""Add append-only evaluation runner scenario attempts."""

from alembic import op
from evaluation.framework.models import EvaluationScenarioExecutionModel

revision = "0004_evaluation_runner"
down_revision = "0003_evaluation_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    EvaluationScenarioExecutionModel.__table__.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    EvaluationScenarioExecutionModel.__table__.drop(op.get_bind(), checkfirst=False)
