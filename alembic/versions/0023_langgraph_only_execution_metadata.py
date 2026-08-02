"""Make LangGraph the only persisted workflow engine.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE investigations SET workflow_engine = 'LangGraph', "
            "execution_mode = 'LANGGRAPH', fallback_used = false, fallback_reason = ''"
        )
    )
    with op.batch_alter_table("investigations") as batch:
        batch.alter_column("workflow_engine", server_default="LangGraph")
        batch.alter_column("execution_mode", server_default="LANGGRAPH")
        batch.alter_column("fallback_used", server_default=sa.false())


def downgrade() -> None:
    with op.batch_alter_table("investigations") as batch:
        batch.alter_column("workflow_engine", server_default="Legacy")
        batch.alter_column("execution_mode", server_default="LEGACY")
