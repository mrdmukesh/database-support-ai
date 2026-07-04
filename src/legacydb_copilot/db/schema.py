from __future__ import annotations

from sqlalchemy import inspect, text

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
    "report_snapshot_json": "TEXT NOT NULL DEFAULT ''",
}

_AUDIT_COLUMNS: dict[str, str] = {
    "workspace_id": "VARCHAR",
    "status": "VARCHAR(40) NOT NULL DEFAULT 'success'",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def initialize_application_schema(database_url: str) -> None:
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
    if not database_url.startswith("sqlite"):
        return
    if "knowledge_articles" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("knowledge_articles")}
    with engine.begin() as connection:
        for column_name, ddl in _KNOWLEDGE_COLUMNS.items():
            if column_name not in existing:
                connection.execute(text(f"ALTER TABLE knowledge_articles ADD COLUMN {column_name} {ddl}"))
