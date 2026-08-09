"""Persist the canonical pgvector knowledge embedding schema.

Revision ID: 0027
Revises: 0026
"""

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "ALTER TABLE knowledge_chunks "
        "ADD COLUMN IF NOT EXISTS embedding vector(1536)"
    )
    # Only embeddings already produced at the canonical OpenAI dimension can
    # be copied safely. Short fallback vectors must be re-embedded, not padded
    # or cast into a semantically invalid representation.
    op.execute(
        "UPDATE knowledge_chunks SET embedding = embedding_json::vector "
        "WHERE embedding IS NULL "
        "AND embedding_json IS NOT NULL "
        "AND embedding_json <> '' "
        "AND jsonb_typeof(embedding_json::jsonb) = 'array' "
        "AND jsonb_array_length(embedding_json::jsonb) = 1536"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_cosine "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_cosine")
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding")
    # The extension may be shared by other application objects; do not drop it.
