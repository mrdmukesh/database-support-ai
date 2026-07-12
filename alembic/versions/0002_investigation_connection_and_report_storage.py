"""Persist investigation connection and report storage references."""

from alembic import op
import sqlalchemy as sa

revision = "0002_investigation_connection_and_report_storage"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column("connection_id", sa.String(), nullable=False, server_default=""))
    op.add_column("investigations", sa.Column("connection_name", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("investigations", sa.Column("report_storage_json", sa.Text(), nullable=False, server_default="{}"))
    op.create_index("ix_investigations_connection_id", "investigations", ["connection_id"])


def downgrade() -> None:
    op.drop_index("ix_investigations_connection_id", table_name="investigations")
    op.drop_column("investigations", "report_storage_json")
    op.drop_column("investigations", "connection_name")
    op.drop_column("investigations", "connection_id")
