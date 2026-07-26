"""Backfill trusted scan metadata for the canonical evaluation workspace."""

from alembic import op
import sqlalchemy as sa


revision = "0011_demo_evaluation_connection_metadata"
down_revision = "0010_connection_scan_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = sa.table(
        "database_connections",
        sa.column("workspace_id", sa.String()),
        sa.column("environment_type", sa.String()),
    )
    workspace = sa.table(
        "workspaces",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
    )
    evaluation_workspace_ids = sa.select(workspace.c.id).where(
        sa.func.lower(workspace.c.name) == "demo_databases"
    )
    op.execute(
        connection.update()
        .where(connection.c.workspace_id.in_(evaluation_workspace_ids))
        .where(connection.c.environment_type == "production")
        .values(environment_type="evaluation")
    )


def downgrade() -> None:
    # This migration repairs trusted operational metadata. Reverting it to
    # production would silently change runtime safety behavior, so downgrade
    # intentionally preserves the explicit evaluation classification.
    pass
