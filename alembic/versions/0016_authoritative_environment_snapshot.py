"""Persist authoritative immutable investigation environment snapshots.

Revision ID: 0016_environment_snapshot
Revises: 0015_safe_planner
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "0016_environment_snapshot"
down_revision = "0015_safe_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("database_connections", "environment_type", server_default=None)
    op.alter_column("investigations", "environment_type", server_default=None)
    op.alter_column("investigations", "policy_name", server_default=None)
    op.alter_column(
        "llm_invocation_audit",
        "environment_type",
        server_default="UNRESOLVED",
    )
    op.alter_column(
        "llm_invocation_audit",
        "policy_name",
        server_default="UNRESOLVED_STRICT_READ_ONLY",
    )
    op.add_column("investigations", sa.Column("selected_database_name", sa.String(255), nullable=True))
    op.add_column("investigations", sa.Column("safety_profile", sa.String(80), nullable=True))
    op.add_column("investigations", sa.Column("environment_source", sa.String(120), nullable=True))
    op.add_column("investigations", sa.Column("environment_snapshot_json", sa.Text(), nullable=True))
    op.add_column("investigations", sa.Column("environment_telemetry_json", sa.Text(), nullable=True))
    investigations = sa.table(
        "investigations",
        sa.column("id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column("connection_id", sa.String()),
        sa.column("connection_name", sa.String()),
        sa.column("environment_type", sa.String()),
        sa.column("selected_database_name", sa.String()),
        sa.column("safety_profile", sa.String()),
        sa.column("environment_source", sa.String()),
        sa.column("environment_snapshot_json", sa.Text()),
        sa.column("environment_telemetry_json", sa.Text()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            investigations.c.id,
            investigations.c.workspace_id,
            investigations.c.connection_id,
            investigations.c.connection_name,
            investigations.c.environment_type,
        )
    ).mappings()
    aliases = {
        "production": "PRODUCTION",
        "test": "TEST",
        "uat": "DEVELOPMENT",
        "development": "DEVELOPMENT",
        "evaluation": "DEMO",
        "demo": "DEMO",
    }
    for row in rows:
        environment = aliases.get((row["environment_type"] or "").casefold(), "UNRESOLVED")
        profile = (
            "PRODUCTION_STRICT_READ_ONLY"
            if environment == "PRODUCTION"
            else "NON_PRODUCTION_DEEP_READ_ONLY"
        )
        snapshot = {
            "selected_connection_id": row["connection_id"],
            "selected_database_name": row["connection_name"],
            "workspace_id": row["workspace_id"],
            "environment_type": environment,
            "safety_profile": profile,
            "environment_source": "Historical investigation record",
            "procedure_execution_permitted": environment != "PRODUCTION",
            "data_modification_permitted": False,
        }
        connection.execute(
            investigations.update()
            .where(investigations.c.id == row["id"])
            .values(
                selected_database_name=row["connection_name"],
                safety_profile=profile,
                environment_source="Historical investigation record",
                environment_snapshot_json=json.dumps(snapshot),
                environment_telemetry_json=json.dumps(
                    {
                        "request_environment": None,
                        "registered_environment": row["environment_type"],
                        "resolved_environment": environment,
                        "safety_profile": profile,
                        "environment_resolution_reason": "historical_record_backfill",
                        "environment_mismatch_detected": False,
                    }
                ),
            )
        )
    for column in (
        "selected_database_name",
        "safety_profile",
        "environment_source",
        "environment_snapshot_json",
        "environment_telemetry_json",
    ):
        op.alter_column("investigations", column, nullable=False)


def downgrade() -> None:
    for column in (
        "environment_telemetry_json",
        "environment_snapshot_json",
        "environment_source",
        "safety_profile",
        "selected_database_name",
    ):
        op.drop_column("investigations", column)
    op.alter_column("database_connections", "environment_type", server_default="production")
    op.alter_column("investigations", "environment_type", server_default="production")
    op.alter_column("investigations", "policy_name", server_default="production_strict")
    op.alter_column("llm_invocation_audit", "environment_type", server_default="production")
    op.alter_column("llm_invocation_audit", "policy_name", server_default="production_strict")
