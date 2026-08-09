from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "migration_0027",
    Path("alembic/versions/0027_pgvector_knowledge_embeddings.py"),
)
assert spec is not None and spec.loader is not None
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class RecordingOperations:
    def __init__(self, dialect: str) -> None:
        self.dialect = dialect
        self.statements: list[str] = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect))

    def execute(self, statement: str) -> None:
        self.statements.append(statement)


def test_pgvector_migration_uses_canonical_dimension_and_safe_backfill(monkeypatch) -> None:
    operations = RecordingOperations("postgresql")
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    sql = "\n".join(operations.statements)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "embedding vector(1536)" in sql
    assert "jsonb_array_length(embedding_json::jsonb) = 1536" in sql
    assert "ix_knowledge_chunks_embedding_cosine" in sql


def test_pgvector_migration_is_noop_for_sqlite(monkeypatch) -> None:
    operations = RecordingOperations("sqlite")
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()
    migration.downgrade()

    assert operations.statements == []


def test_pgvector_downgrade_preserves_shared_extension(monkeypatch) -> None:
    operations = RecordingOperations("postgresql")
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    sql = "\n".join(operations.statements)
    assert "DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_cosine" in sql
    assert "DROP COLUMN IF EXISTS embedding" in sql
    assert "DROP EXTENSION" not in sql
