from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.session import create_db_engine

_KNOWLEDGE_COLUMNS: dict[str, str] = {
    "body": "TEXT NOT NULL DEFAULT ''",
    "module_name": "VARCHAR(120) NOT NULL DEFAULT ''",
    "issue_type": "VARCHAR(120) NOT NULL DEFAULT ''",
    "symptoms": "TEXT NOT NULL DEFAULT ''",
    "detected_entities": "TEXT NOT NULL DEFAULT '[]'",
    "actual_root_cause": "TEXT NOT NULL DEFAULT ''",
    "fix_summary": "TEXT NOT NULL DEFAULT ''",
    "sql_changed": "TEXT NOT NULL DEFAULT ''",
    "procedures_changed": "TEXT NOT NULL DEFAULT ''",
    "test_cases": "TEXT NOT NULL DEFAULT ''",
    "proof_of_fix": "TEXT NOT NULL DEFAULT ''",
    "rollback_plan": "TEXT NOT NULL DEFAULT ''",
    "severity": "VARCHAR(40) NOT NULL DEFAULT 'medium'",
    "confidence_after_approval": "NUMERIC(5, 4)",
    "approved_at": "DATETIME",
    "source_investigation_id": "VARCHAR",
    "is_active": "BOOLEAN NOT NULL DEFAULT 1",
    "indexed_at": "DATETIME",
}

_INVESTIGATION_COLUMNS: dict[str, str] = {
    "connection_id": "VARCHAR NOT NULL DEFAULT ''",
    "connection_name": "VARCHAR(255) NOT NULL DEFAULT ''",
    "report_storage_json": "TEXT NOT NULL DEFAULT '{}'",
    "report_snapshot_json": "TEXT NOT NULL DEFAULT ''",
    "ai_debug_trace_json": "TEXT NOT NULL DEFAULT ''",
    "llm_audit_outcome": "VARCHAR(80) NOT NULL DEFAULT ''",
    "llm_audit_reason": "TEXT NOT NULL DEFAULT ''",
    "workflow_engine": "VARCHAR(40) NOT NULL DEFAULT 'LangGraph'",
    "execution_mode": "VARCHAR(40) NOT NULL DEFAULT 'LANGGRAPH'",
    "graph_version": "VARCHAR(80) NOT NULL DEFAULT ''",
    "graph_execution_id": "VARCHAR(120) NOT NULL DEFAULT ''",
    "requested_model": "VARCHAR(120) NOT NULL DEFAULT ''",
    "effective_model": "VARCHAR(120) NOT NULL DEFAULT ''",
    "execution_provider": "VARCHAR(80) NOT NULL DEFAULT ''",
    "reasoning_effort": "VARCHAR(40) NOT NULL DEFAULT ''",
    "selected_by": "VARCHAR(40) NOT NULL DEFAULT 'Automatic'",
    "execution_policy_version": "VARCHAR(40) NOT NULL DEFAULT ''",
    "fallback_used": "BOOLEAN NOT NULL DEFAULT 0",
    "fallback_reason": "TEXT NOT NULL DEFAULT ''",
    "requested_model_mode": "VARCHAR(40) NOT NULL DEFAULT ''",
    "requested_catalog_model_id": "VARCHAR(36) NOT NULL DEFAULT ''",
    "effective_catalog_model_id": "VARCHAR(36) NOT NULL DEFAULT ''",
    "model_snapshot_json": "TEXT NOT NULL DEFAULT '{}'",
    "model_policy_decision": "VARCHAR(40) NOT NULL DEFAULT ''",
    "model_policy_decision_reason": "TEXT NOT NULL DEFAULT ''",
    "model_entitlement_source": "VARCHAR(120) NOT NULL DEFAULT ''",
    "model_selection_source": "VARCHAR(40) NOT NULL DEFAULT ''",
    "model_selection_requested_at": "TIMESTAMP",
    "model_selection_configuration_version": "INTEGER NOT NULL DEFAULT 0",
    "execution_started_at": "TIMESTAMP",
    "execution_ended_at": "TIMESTAMP",
}

_AUDIT_COLUMNS: dict[str, str] = {
    "workspace_id": "VARCHAR",
    "status": "VARCHAR(40) NOT NULL DEFAULT 'success'",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

_LLM_AUDIT_COLUMNS: dict[str, str] = {
    "provider_request_id": "VARCHAR(160)",
}

_VERIFICATION_COLUMNS: dict[str, str] = {
    "purpose": "TEXT NOT NULL DEFAULT ''",
    "claim_being_verified": "TEXT NOT NULL DEFAULT ''",
    "evidence_logic": "TEXT NOT NULL DEFAULT ''",
    "expected_result_explanation": "TEXT NOT NULL DEFAULT ''",
    "interpretation": "TEXT NOT NULL DEFAULT ''",
    "conclusion_template": "TEXT NOT NULL DEFAULT ''",
    "parameters": "TEXT NOT NULL DEFAULT '{}'",
    "parameter_types": "TEXT NOT NULL DEFAULT '{}'",
    "evidence_id": "VARCHAR(120) NOT NULL DEFAULT ''",
    "entity_table": "VARCHAR(255) NOT NULL DEFAULT ''",
    "resolved_entity_scope": "VARCHAR(120) NOT NULL DEFAULT ''",
    "identifier_column": "VARCHAR(255) NOT NULL DEFAULT ''",
    "identifier_value": "TEXT",
    "read_only": "BOOLEAN NOT NULL DEFAULT 1",
    "actual_result": "TEXT NOT NULL DEFAULT '{}'",
}


def _try_enable_pgvector(
    connection,
    *,
    add_embedding_column: bool = True,
    add_embedding_index: bool = True,
) -> bool:
    try:
        # A compatibility DDL statement must never hold application startup
        # behind an unrelated long-running transaction.
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        if add_embedding_column:
            connection.execute(text("ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding vector(1536)"))
        if add_embedding_index:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_cosine "
                    "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)"
                )
            )
        return True
    except SQLAlchemyError:
        return False


def initialize_application_schema(database_url: str) -> None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Initializes and gently migrates the internal application metadata database.
    Input:
        SQLAlchemy database URL for the app database.
    Output:
        Tables and compatibility columns required by the API, including pgvector support when available.
    Called by:
        FastAPI startup in api.py.
    Flow:
        App startup -> schema initialization -> routers/services persist investigations and reports.
    Safety:
        Mutates only the internal app database; customer databases are never migrated here.
    """

    engine = create_db_engine(database_url)
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    if "investigations" in inspector.get_table_names():
        existing_investigation_columns = {column["name"] for column in inspector.get_columns("investigations")}
        with engine.begin() as connection:
            for column_name, ddl in _INVESTIGATION_COLUMNS.items():
                if column_name not in existing_investigation_columns:
                    connection.execute(text(f"ALTER TABLE investigations ADD COLUMN {column_name} {ddl}"))
    if "audit_logs" in inspector.get_table_names():
        existing_audit_columns = {column["name"] for column in inspector.get_columns("audit_logs")}
        with engine.begin() as connection:
            for column_name, ddl in _AUDIT_COLUMNS.items():
                if column_name not in existing_audit_columns:
                    connection.execute(text(f"ALTER TABLE audit_logs ADD COLUMN {column_name} {ddl}"))
    if "llm_invocation_audit" in inspector.get_table_names():
        existing_llm_audit_columns = {
            column["name"] for column in inspector.get_columns("llm_invocation_audit")
        }
        with engine.begin() as connection:
            for column_name, ddl in _LLM_AUDIT_COLUMNS.items():
                if column_name not in existing_llm_audit_columns:
                    connection.execute(
                        text(f"ALTER TABLE llm_invocation_audit ADD COLUMN {column_name} {ddl}")
                    )
    if "verification_checks" in inspector.get_table_names():
        existing_verification_columns = {column["name"] for column in inspector.get_columns("verification_checks")}
        with engine.begin() as connection:
            for column_name, ddl in _VERIFICATION_COLUMNS.items():
                if column_name not in existing_verification_columns:
                    connection.execute(text(f"ALTER TABLE verification_checks ADD COLUMN {column_name} {ddl}"))
    if engine.dialect.name == "postgresql" and "knowledge_chunks" in inspector.get_table_names():
        knowledge_columns = {column["name"] for column in inspector.get_columns("knowledge_chunks")}
        knowledge_indexes = {index["name"] for index in inspector.get_indexes("knowledge_chunks")}
        add_embedding_column = "embedding" not in knowledge_columns
        add_embedding_index = "ix_knowledge_chunks_embedding_cosine" not in knowledge_indexes
        if add_embedding_column or add_embedding_index:
            with engine.begin() as connection:
                _try_enable_pgvector(
                    connection,
                    add_embedding_column=add_embedding_column,
                    add_embedding_index=add_embedding_index,
                )
    if not database_url.startswith("sqlite"):
        return
    if "knowledge_articles" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("knowledge_articles")}
    with engine.begin() as connection:
        for column_name, ddl in _KNOWLEDGE_COLUMNS.items():
            if column_name not in existing:
                connection.execute(text(f"ALTER TABLE knowledge_articles ADD COLUMN {column_name} {ddl}"))
