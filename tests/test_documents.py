from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from legacydb_copilot.common import DomainError
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import DocumentModel, DocumentVersionModel, KnowledgeChunkModel, OrganizationModel, UserModel, WorkspaceModel
from legacydb_copilot.db.schema import _try_enable_pgvector
from legacydb_copilot.documents import (
    DocumentVersion,
    UploadPolicy,
    content_sha256,
    detect_mime_type,
    is_duplicate,
)
from legacydb_copilot.services.rag_retrieval_service import (
    KnowledgeQuery,
    PgVectorKnowledgeRetriever,
    SQLiteKnowledgeRetriever,
    chunk_text,
    embed_text,
    keyword_fallback_retrieve,
)
from legacydb_copilot.services.storage_service import get_app_storage


def test_upload_policy_allows_required_file_types() -> None:
    policy = UploadPolicy(max_size_bytes=100)
    policy.validate("runbook.pdf", 10)
    policy.validate("script.sql", 10)
    policy.validate("notes.md", 10)


def test_upload_policy_rejects_bad_extension_and_large_file() -> None:
    policy = UploadPolicy(max_size_bytes=10)

    with pytest.raises(DomainError, match="Unsupported file extension"):
        policy.validate("malware.exe", 1)

    with pytest.raises(DomainError, match="maximum size"):
        policy.validate("large.pdf", 11)


def test_document_hash_duplicate_detection() -> None:
    content = b"legacy procedure notes"
    known = {content_sha256(content)}

    assert is_duplicate(content, known)
    assert not is_duplicate(b"different", known)


def test_document_version_records_workspace_owner_and_mime_type() -> None:
    version = DocumentVersion(
        document_id=uuid4(),
        version=1,
        filename="guide.pdf",
        owner_id=uuid4(),
        workspace_id=uuid4(),
        sha256=content_sha256(b"pdf"),
        mime_type=detect_mime_type("guide.pdf"),
    )

    assert version.mime_type == "application/pdf"


def _memory_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def test_sqlite_knowledge_retriever_indexes_chunks_and_semantic_searches(tmp_path) -> None:
    db = _memory_session()
    org = OrganizationModel(name="Knowledge Org", slug="knowledge-org")
    db.add(org)
    db.flush()
    user = UserModel(organization_id=org.id, email="k@example.com", full_name="Knowledge User", role="organization_admin")
    workspace = WorkspaceModel(organization_id=org.id, name="Ops", slug="ops")
    db.add_all([user, workspace])
    db.flush()
    path = tmp_path / "runbook.md"
    path.write_text(
        "Module: gate\nBusiness Object: event\nIssue: duplicate\n"
        "Duplicate GATE_IN events can happen when retry processing inserts without an idempotency key.\n"
        "Procedure sp_retry_gate_events writes gate events.",
        encoding="utf-8",
    )
    document = DocumentModel(organization_id=org.id, workspace_id=workspace.id, owner_id=user.id, title="Gate Event Runbook")
    db.add(document)
    db.flush()
    version = DocumentVersionModel(
        document_id=document.id,
        version=1,
        filename=path.name,
        mime_type="text/markdown",
        size_bytes=path.stat().st_size,
        sha256=content_sha256(path.read_bytes()),
        storage_key=str(path),
    )
    db.add(version)
    db.flush()

    retriever = SQLiteKnowledgeRetriever()
    indexed = retriever.index_document(
        db,
        organization_id=org.id,
        workspace_id=workspace.id,
        document=document,
        version=version,
    )
    db.commit()
    results = retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=org.id,
            workspace_id=workspace.id,
            question="Why did container MSCU1005 create duplicate GATE_IN events?",
            top_k=3,
        ),
    )

    assert indexed >= 1
    assert db.query(KnowledgeChunkModel).count() >= 1
    stored_chunk = db.query(KnowledgeChunkModel).first()
    assert stored_chunk is not None
    assert stored_chunk.embedding_json
    assert len(embed_text("duplicate gate event")) == 128
    assert results
    assert results[0].metadata["retriever"] == "sqlite-vector"
    assert "GATE_IN" in results[0].snippet


def test_uploaded_markdown_body_is_extracted_chunked_and_retrieved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    db = _memory_session()
    org = OrganizationModel(name="Upload Body Org", slug="upload-body-org")
    db.add(org)
    db.flush()
    user = UserModel(organization_id=org.id, email="body@example.com", full_name="Body User", role="organization_admin")
    workspace = WorkspaceModel(organization_id=org.id, name="Ops", slug="ops")
    db.add_all([user, workspace])
    db.flush()
    body = (
        "# Retry Runbook\n\n"
        "Appointment APT-2005 can create duplicate lab orders when retry processing lacks an idempotency guard.\n"
        "Procedure sp_retry_failed_lab_orders writes lab_orders after checking appointment_number."
    )
    storage_key = "documents/upload-body/runbook.md"
    get_app_storage().save_bytes(storage_key, body.encode("utf-8"), "text/markdown")
    document = DocumentModel(organization_id=org.id, workspace_id=workspace.id, owner_id=user.id, title="Retry Runbook")
    db.add(document)
    db.flush()
    version = DocumentVersionModel(
        document_id=document.id,
        version=1,
        filename="runbook.md",
        mime_type="text/markdown",
        size_bytes=len(body.encode("utf-8")),
        sha256=content_sha256(body.encode("utf-8")),
        storage_key=storage_key,
    )
    db.add(version)
    db.flush()

    retriever = SQLiteKnowledgeRetriever()
    retriever.index_document(
        db,
        organization_id=org.id,
        workspace_id=workspace.id,
        document=document,
        version=version,
    )
    db.commit()

    chunk = db.query(KnowledgeChunkModel).one()
    results = retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=org.id,
            workspace_id=workspace.id,
            question="Why does APT-2005 create duplicate lab orders?",
        ),
    )

    assert "duplicate lab orders" in chunk.content
    assert "Uploaded document text extraction unavailable" not in chunk.content
    assert results
    assert "duplicate lab orders" in results[0].snippet


def test_workspace_isolation_for_retrieved_knowledge(tmp_path) -> None:
    db = _memory_session()
    org = OrganizationModel(name="Isolation Org", slug="isolation-org")
    db.add(org)
    db.flush()
    user = UserModel(organization_id=org.id, email="i@example.com", full_name="Isolation User", role="organization_admin")
    workspace_a = WorkspaceModel(organization_id=org.id, name="A", slug="a")
    workspace_b = WorkspaceModel(organization_id=org.id, name="B", slug="b")
    db.add_all([user, workspace_a, workspace_b])
    db.flush()
    path = tmp_path / "workspace-b.md"
    path.write_text("Private duplicate shipment retry notes for workspace B only.", encoding="utf-8")
    document = DocumentModel(organization_id=org.id, workspace_id=workspace_b.id, owner_id=user.id, title="Workspace B Notes")
    db.add(document)
    db.flush()
    version = DocumentVersionModel(
        document_id=document.id,
        version=1,
        filename=path.name,
        mime_type="text/markdown",
        size_bytes=path.stat().st_size,
        sha256=content_sha256(path.read_bytes()),
        storage_key=str(path),
    )
    db.add(version)
    db.flush()

    retriever = SQLiteKnowledgeRetriever()
    retriever.index_document(
        db,
        organization_id=org.id,
        workspace_id=workspace_b.id,
        document=document,
        version=version,
    )
    db.commit()

    workspace_a_results = retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=org.id,
            workspace_id=workspace_a.id,
            question="duplicate shipment retry",
        ),
    )
    workspace_b_results = retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=org.id,
            workspace_id=workspace_b.id,
            question="duplicate shipment retry",
        ),
    )

    assert workspace_a_results == []
    assert workspace_b_results


def test_embedding_and_chunking_are_deterministic() -> None:
    text = "duplicate gate event retry idempotency " * 80

    assert chunk_text(text, max_tokens=20, overlap=5)
    assert embed_text("duplicate gate event") == embed_text("duplicate gate event")


def test_pgvector_missing_openai_key_falls_back_safely(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_RETRIEVER_BACKEND", "pgvector")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = _memory_session()
    org = OrganizationModel(name="PgVector Fallback Org", slug="pgvector-fallback-org")
    db.add(org)
    db.flush()
    user = UserModel(organization_id=org.id, email="p@example.com", full_name="PgVector User", role="organization_admin")
    workspace = WorkspaceModel(organization_id=org.id, name="Ops", slug="ops")
    db.add_all([user, workspace])
    db.flush()
    path = tmp_path / "fallback.md"
    path.write_text("Approved runbook says duplicate retry needs idempotency.", encoding="utf-8")
    document = DocumentModel(organization_id=org.id, workspace_id=workspace.id, owner_id=user.id, title="Fallback Runbook")
    db.add(document)
    db.flush()
    version = DocumentVersionModel(
        document_id=document.id,
        version=1,
        filename=path.name,
        mime_type="text/markdown",
        size_bytes=path.stat().st_size,
        sha256=content_sha256(path.read_bytes()),
        storage_key=str(path),
    )
    db.add(version)
    db.flush()

    retriever = PgVectorKnowledgeRetriever()
    indexed = retriever.index_document(
        db,
        organization_id=org.id,
        workspace_id=workspace.id,
        document=document,
        version=version,
    )
    db.commit()
    results = retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=org.id,
            workspace_id=workspace.id,
            question="duplicate retry idempotency",
        ),
    )

    assert indexed >= 1
    assert results
    assert results[0].metadata["retriever"] == "sqlite-vector"


def test_pgvector_schema_setup_is_non_fatal_when_extension_is_unavailable() -> None:
    class UnsupportedVectorConnection:
        def execute(self, statement):
            raise SQLAlchemyError("extension vector is not allow-listed")

    assert _try_enable_pgvector(UnsupportedVectorConnection()) is False


def test_keyword_fallback_returns_documents_when_no_vectors(tmp_path) -> None:
    db = _memory_session()
    org = OrganizationModel(name="Fallback Org", slug="fallback-org")
    db.add(org)
    db.flush()
    user = UserModel(organization_id=org.id, email="f@example.com", full_name="Fallback User", role="organization_admin")
    workspace = WorkspaceModel(organization_id=org.id, name="Ops", slug="ops")
    db.add_all([user, workspace])
    db.flush()
    path = tmp_path / "notes.txt"
    path.write_text("Duplicate event retry notes", encoding="utf-8")
    document = DocumentModel(organization_id=org.id, workspace_id=workspace.id, owner_id=user.id, title="Retry Notes")
    db.add(document)
    db.flush()
    db.add(
        DocumentVersionModel(
            document_id=document.id,
            version=1,
            filename=path.name,
            mime_type="text/plain",
            size_bytes=path.stat().st_size,
            sha256=content_sha256(path.read_bytes()),
            storage_key=str(path),
        )
    )
    db.commit()

    results = keyword_fallback_retrieve(
        db,
        KnowledgeQuery(
            organization_id=org.id,
            workspace_id=workspace.id,
            question="duplicate retry event",
        ),
    )

    assert results
    assert results[0].source == "keyword-fallback"
