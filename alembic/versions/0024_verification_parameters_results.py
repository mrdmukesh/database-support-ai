"""Persist verification bind parameters and structured results.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = (
        sa.Column("parameters", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("parameter_types", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("evidence_id", sa.String(120), nullable=False, server_default=""),
        sa.Column("entity_table", sa.String(255), nullable=False, server_default=""),
        sa.Column("resolved_entity_scope", sa.String(120), nullable=False, server_default=""),
        sa.Column("identifier_column", sa.String(255), nullable=False, server_default=""),
        sa.Column("identifier_value", sa.Text()),
        sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("actual_result", sa.Text(), nullable=False, server_default="{}"),
    )
    for column in columns:
        op.add_column("verification_checks", column)


def downgrade() -> None:
    for name in (
        "actual_result", "read_only", "identifier_value", "identifier_column",
        "resolved_entity_scope", "entity_table", "evidence_id", "parameter_types", "parameters",
    ):
        op.drop_column("verification_checks", name)
