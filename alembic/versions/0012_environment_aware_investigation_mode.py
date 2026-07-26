"""Persist trusted investigation and LLM audit policy context."""

from alembic import op
import sqlalchemy as sa


revision = "0012_environment_aware_investigation_mode"
down_revision = "0011_demo_evaluation_connection_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_database_connections_environment_type",
        "database_connections",
        type_="check",
    )
    op.execute(
        "UPDATE database_connections SET environment_type = 'uat' "
        "WHERE environment_type = 'non_production'"
    )
    op.create_check_constraint(
        "ck_database_connections_environment_type",
        "database_connections",
        "environment_type IN ('production','uat','test','evaluation','demo')",
    )
    op.add_column("investigations", sa.Column("environment_type", sa.String(40), nullable=False, server_default="production"))
    op.add_column("investigations", sa.Column("policy_name", sa.String(80), nullable=False, server_default="production_strict"))
    op.add_column("investigations", sa.Column("policy_version", sa.String(40), nullable=False, server_default="v1"))
    op.add_column("investigations", sa.Column("policy_audit_json", sa.Text(), nullable=False, server_default="{}"))
    op.create_index("ix_investigations_environment_type", "investigations", ["environment_type"])
    op.add_column("llm_invocation_audit", sa.Column("connection_id", sa.String(36), nullable=True))
    op.add_column("llm_invocation_audit", sa.Column("environment_type", sa.String(40), nullable=False, server_default="production"))
    op.add_column("llm_invocation_audit", sa.Column("policy_name", sa.String(80), nullable=False, server_default="production_strict"))
    op.add_column("llm_invocation_audit", sa.Column("policy_version", sa.String(40), nullable=False, server_default="v1"))
    op.create_index("ix_llm_invocation_audit_connection_id", "llm_invocation_audit", ["connection_id"])
    op.create_index("ix_llm_invocation_audit_environment_type", "llm_invocation_audit", ["environment_type"])


def downgrade() -> None:
    op.drop_index("ix_llm_invocation_audit_environment_type", table_name="llm_invocation_audit")
    op.drop_index("ix_llm_invocation_audit_connection_id", table_name="llm_invocation_audit")
    for column in ("policy_version", "policy_name", "environment_type", "connection_id"):
        op.drop_column("llm_invocation_audit", column)
    op.drop_index("ix_investigations_environment_type", table_name="investigations")
    for column in ("policy_audit_json", "policy_version", "policy_name", "environment_type"):
        op.drop_column("investigations", column)
    op.drop_constraint("ck_database_connections_environment_type", "database_connections", type_="check")
    op.create_check_constraint(
        "ck_database_connections_environment_type",
        "database_connections",
        "environment_type IN ('production','non_production','evaluation','demo','test')",
    )
