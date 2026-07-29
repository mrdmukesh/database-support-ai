"""Persist authoritative immutable investigation environment snapshots.

Revision ID: 0016_environment_snapshot
Revises: 0015_safe_planner
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "0016_environment_snapshot"
down_revision = "0015_safe_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    investigation_columns = {
        column["name"] for column in inspector.get_columns("investigations")
    }
    op.alter_column(
        "database_connections",
        "environment_type",
        existing_type=sa.String(40),
        server_default=None,
    )
    op.alter_column(
        "investigations",
        "environment_type",
        existing_type=sa.String(40),
        server_default=None,
    )
    op.alter_column(
        "investigations",
        "policy_name",
        existing_type=sa.String(80),
        server_default=None,
    )
    op.alter_column(
        "llm_invocation_audit",
        "environment_type",
        existing_type=sa.String(40),
        server_default="UNRESOLVED",
    )
    op.alter_column(
        "llm_invocation_audit",
        "policy_name",
        existing_type=sa.String(80),
        server_default="UNRESOLVED_STRICT_READ_ONLY",
    )
    new_columns = (
        sa.Column("selected_database_name", sa.String(255), nullable=True),
        sa.Column("safety_profile", sa.String(80), nullable=True),
        sa.Column("environment_source", sa.String(120), nullable=True),
        sa.Column("environment_snapshot_json", sa.Text(), nullable=True),
        sa.Column("environment_telemetry_json", sa.Text(), nullable=True),
    )
    for column in new_columns:
        if column.name not in investigation_columns:
            op.add_column("investigations", column)
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
            investigations.c.selected_database_name,
            investigations.c.safety_profile,
            investigations.c.environment_source,
            investigations.c.environment_snapshot_json,
            investigations.c.environment_telemetry_json,
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
        backfill = {
            "selected_database_name": row["connection_name"],
            "safety_profile": profile,
            "environment_source": "Historical investigation record",
            "environment_snapshot_json": json.dumps(snapshot),
            "environment_telemetry_json": json.dumps(
                {
                    "request_environment": None,
                    "registered_environment": row["environment_type"],
                    "resolved_environment": environment,
                    "safety_profile": profile,
                    "environment_resolution_reason": "historical_record_backfill",
                    "environment_mismatch_detected": False,
                }
            ),
        }
        missing_values = {key: value for key, value in backfill.items() if row[key] is None}
        if missing_values:
            connection.execute(
                investigations.update()
                .where(investigations.c.id == row["id"])
                .values(**missing_values)
            )
    for column in (
        "selected_database_name",
        "safety_profile",
        "environment_source",
        "environment_snapshot_json",
        "environment_telemetry_json",
    ):
        op.alter_column(
            "investigations",
            column,
            existing_type=sa.Text()
            if column.endswith("_json")
            else sa.String(255)
            if column == "selected_database_name"
            else sa.String(120)
            if column == "environment_source"
            else sa.String(80),
            nullable=False,
        )


def downgrade() -> None:
    for column in (
        "environment_telemetry_json",
        "environment_snapshot_json",
        "environment_source",
        "safety_profile",
        "selected_database_name",
    ):
        op.drop_column("investigations", column)
    op.alter_column(
        "database_connections",
        "environment_type",
        existing_type=sa.String(40),
        server_default="production",
    )
    op.alter_column(
        "investigations",
        "environment_type",
        existing_type=sa.String(40),
        server_default="production",
    )
    op.alter_column(
        "investigations",
        "policy_name",
        existing_type=sa.String(80),
        server_default="production_strict",
    )
    op.alter_column(
        "llm_invocation_audit",
        "environment_type",
        existing_type=sa.String(40),
        server_default="production",
    )
    op.alter_column(
        "llm_invocation_audit",
        "policy_name",
        existing_type=sa.String(80),
        server_default="production_strict",
    )
