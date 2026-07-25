"""Add trusted environment-aware scan policy metadata to database connections."""

from alembic import op
import sqlalchemy as sa


revision = "0010_connection_scan_policy"
down_revision = "0009_llm_audit_outcomes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "database_connections",
        sa.Column("environment_type", sa.String(40), nullable=False, server_default="production"),
    )
    op.add_column(
        "database_connections",
        sa.Column("max_scan_rows", sa.Integer(), nullable=False, server_default="500"),
    )
    op.create_check_constraint(
        "ck_database_connections_environment_type",
        "database_connections",
        "environment_type IN ('production','non_production','evaluation','demo','test')",
    )
    op.create_check_constraint(
        "ck_database_connections_max_scan_rows",
        "database_connections",
        "max_scan_rows >= 1 AND max_scan_rows <= 5000",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_database_connections_max_scan_rows",
        "database_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_database_connections_environment_type",
        "database_connections",
        type_="check",
    )
    op.drop_column("database_connections", "max_scan_rows")
    op.drop_column("database_connections", "environment_type")

