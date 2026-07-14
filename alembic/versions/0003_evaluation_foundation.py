"""Add isolated research evaluation foundation tables."""

from alembic import op
from evaluation.framework import models as evaluation_models

revision = "0003_evaluation_foundation"
down_revision = "0002_investigation_connection_and_report_storage"
branch_labels = None
depends_on = None

TABLES = (
    evaluation_models.EvaluationRunModel.__table__,
    evaluation_models.TestScenarioModel.__table__,
    evaluation_models.ScenarioExpectedObjectModel.__table__,
    evaluation_models.ScenarioExpectedEvidenceModel.__table__,
    evaluation_models.ScenarioAcceptableFixModel.__table__,
    evaluation_models.EvaluationInvestigationResultModel.__table__,
    evaluation_models.InvestigationEvidenceSnapshotModel.__table__,
    evaluation_models.InvestigationSQLSnapshotModel.__table__,
    evaluation_models.DeterministicValidationResultModel.__table__,
    evaluation_models.AIJudgeResultModel.__table__,
    evaluation_models.HumanReviewModel.__table__,
    evaluation_models.CapabilityResultModel.__table__,
    evaluation_models.EvaluationMetricModel.__table__,
    evaluation_models.EvaluationArtifactModel.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind, checkfirst=False)
