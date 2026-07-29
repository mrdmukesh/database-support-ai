"""Persist deterministic evidence-gap analysis."""

import sqlalchemy as sa

from alembic import op

revision = "0014_evidence_gaps"
down_revision = "0013_investigation_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigations",
        sa.Column(
            "evidence_gap_analysis_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("""('{"status":"NOT_ANALYZED","gaps":[]}')"""),
        ),
    )


def downgrade() -> None:
    op.drop_column("investigations", "evidence_gap_analysis_json")
