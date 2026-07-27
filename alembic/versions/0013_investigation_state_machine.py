"""Add deterministic investigation state transition history."""

from alembic import op
import sqlalchemy as sa


revision = "0013_investigation_state"
down_revision = "0012_env_investigation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_state_transitions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("previous_state", sa.String(80), nullable=False, server_default=""),
        sa.Column("current_state", sa.String(80), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("iteration_number", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investigation_state_transitions_investigation_id",
        "investigation_state_transitions",
        ["investigation_id"],
    )
    op.create_index(
        "ix_investigation_state_transitions_current_state",
        "investigation_state_transitions",
        ["current_state"],
    )
    op.create_index(
        "ix_investigation_state_transitions_transitioned_at",
        "investigation_state_transitions",
        ["transitioned_at"],
    )
    op.create_index(
        "ix_investigation_state_transitions_organization_id",
        "investigation_state_transitions",
        ["organization_id"],
    )
    op.create_index(
        "ix_investigation_state_transitions_workspace_id",
        "investigation_state_transitions",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investigation_state_transitions_workspace_id",
        table_name="investigation_state_transitions",
    )
    op.drop_index(
        "ix_investigation_state_transitions_organization_id",
        table_name="investigation_state_transitions",
    )
    op.drop_index(
        "ix_investigation_state_transitions_transitioned_at",
        table_name="investigation_state_transitions",
    )
    op.drop_index(
        "ix_investigation_state_transitions_current_state",
        table_name="investigation_state_transitions",
    )
    op.drop_index(
        "ix_investigation_state_transitions_investigation_id",
        table_name="investigation_state_transitions",
    )
    op.drop_table("investigation_state_transitions")
