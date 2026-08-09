"""Add versioned structural metadata catalog.

Revision ID: 0025
Revises: 0024
"""

import sqlalchemy as sa

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metadata_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("database_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("schema_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("source_database", sa.String(255), nullable=False, server_default=""),
        sa.Column("discovery_version", sa.String(32), nullable=False, server_default="1"),
        sa.Column("counts_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("completeness_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("changes_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("error_summary", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint(
            "connection_id", "version", name="uq_metadata_snapshot_connection_version"
        ),
    )
    op.create_index(
        "ix_metadata_snapshot_tenant_active",
        "metadata_snapshots",
        ["organization_id", "workspace_id", "connection_id", "is_active"],
    )
    op.create_table(
        "metadata_objects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(36),
            sa.ForeignKey("metadata_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("schema_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("object_name", sa.String(512), nullable=False),
        sa.Column("source_object_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("definition_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("definition", sa.Text),
        sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
        sa.UniqueConstraint(
            "snapshot_id",
            "object_type",
            "schema_name",
            "object_name",
            name="uq_metadata_object_identity",
        ),
    )
    op.create_index(
        "ix_metadata_object_snapshot_name",
        "metadata_objects",
        ["snapshot_id", "schema_name", "object_name"],
    )
    op.create_table(
        "metadata_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(36),
            sa.ForeignKey("metadata_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_key", sa.String(800), nullable=False),
        sa.Column("target_key", sa.String(800), nullable=False),
        sa.Column("relationship_type", sa.String(40), nullable=False),
        sa.Column("source_column", sa.String(255), nullable=False, server_default=""),
        sa.Column("target_column", sa.String(255), nullable=False, server_default=""),
        sa.Column("dependency_distance", sa.Integer, nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
    )
    op.create_index(
        "ix_metadata_relationship_source",
        "metadata_relationships",
        ["snapshot_id", "source_key", "relationship_type"],
    )


def downgrade() -> None:
    op.drop_table("metadata_relationships")
    op.drop_table("metadata_objects")
    op.drop_table("metadata_snapshots")
