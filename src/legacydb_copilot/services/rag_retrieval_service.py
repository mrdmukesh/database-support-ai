from __future__ import annotations

import json
import math
import re
import zipfile
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import DocumentModel, DocumentVersionModel, KnowledgeArticleModel, KnowledgeChunkModel


EMBEDDING_DIMENSIONS = 128


@dataclass(frozen=True)
class RetrievedDocument:
    title: str
    filename: str
    snippet: str
    score: float = 0.0
    source: str = "document"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeChunk:
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class KnowledgeQuery:
    organization_id: str
    workspace_id: str
    question: str
    top_k: int = 8
    metadata_filters: dict[str, str] | None = None


class KnowledgeRetriever(ABC):
    @abstractmethod
    def index_document(
        self,
        db: Session,
        *,
        organization_id: str,
        workspace_id: str,
        document: DocumentModel,
        version: DocumentVersionModel,
    ) -> int:
        """Extract, chunk, embed, and store knowledge for a document."""

    @abstractmethod
    def retrieve(self, db: Session, query: KnowledgeQuery) -> list[RetrievedDocument]:
        """Return top ranked knowledge evidence for a question."""


class SQLiteKnowledgeRetriever(KnowledgeRetriever):
    def index_document(
        self,
        db: Session,
        *,
        organization_id: str,
        workspace_id: str,
        document: DocumentModel,
        version: DocumentVersionModel,
    ) -> int:
        text = extract_text(Path(version.storage_key), version.mime_type)
        if not text.strip():
            text = f"{document.title}\n{version.filename}\nUploaded document text extraction unavailable."
        chunks = chunk_text(text)
        db.query(KnowledgeChunkModel).filter(
            KnowledgeChunkModel.organization_id == organization_id,
            KnowledgeChunkModel.workspace_id == workspace_id,
            KnowledgeChunkModel.document_id == document.id,
            KnowledgeChunkModel.document_version_id == version.id,
        ).delete(synchronize_session=False)
        inferred = infer_metadata(document.title, text)
        for index, chunk in enumerate(chunks):
            chunk_metadata = infer_metadata(document.title, chunk)
            metadata = {**inferred, **{key: value for key, value in chunk_metadata.items() if value}}
            db.add(
                KnowledgeChunkModel(
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    document_id=document.id,
                    document_version_id=version.id,
                    source="document",
                    source_title=document.title,
                    chunk_index=index,
                    content=chunk,
                    embedding_json=json.dumps(embed_text(chunk)),
                    module_name=metadata.get("module", ""),
                    table_name=metadata.get("table", ""),
                    procedure_name=metadata.get("procedure", ""),
                    business_object=metadata.get("business_object", ""),
                    issue_type=metadata.get("issue_type", ""),
                    tags=json.dumps(metadata.get("tags", [])),
                    approval_status="uploaded",
                    confidence=0.65,
                )
            )
        version.indexed_at = _utc_now()
        return len(chunks)

    def retrieve(self, db: Session, query: KnowledgeQuery) -> list[RetrievedDocument]:
        try:
            semantic = self._semantic_search(db, query)
        except Exception:
            semantic = []
        if semantic:
            return semantic
        return keyword_fallback_retrieve(db, query)

    def _semantic_search(self, db: Session, query: KnowledgeQuery) -> list[RetrievedDocument]:
        vector = embed_text(query.question)
        db_query = db.query(KnowledgeChunkModel).filter(
            KnowledgeChunkModel.organization_id == query.organization_id,
            KnowledgeChunkModel.workspace_id == query.workspace_id,
        )
        for field_name, value in (query.metadata_filters or {}).items():
            column = _filter_column(field_name)
            if column is not None and value:
                db_query = db_query.filter(column == value)
        chunks = db_query.order_by(KnowledgeChunkModel.updated_at.desc()).limit(500).all()
        scored: list[tuple[float, KnowledgeChunkModel]] = []
        question_tokens = set(tokenize(query.question))
        for chunk in chunks:
            chunk_vector = _loads_vector(chunk.embedding_json)
            semantic_score = cosine_similarity(vector, chunk_vector)
            token_score = len(question_tokens & set(tokenize(chunk.content))) / max(1, len(question_tokens))
            metadata_score = _metadata_score(question_tokens, chunk)
            score = semantic_score * 0.72 + token_score * 0.18 + metadata_score * 0.10
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedDocument(
                title=chunk.source_title,
                filename=chunk.source_title,
                snippet=chunk.content,
                score=round(score, 4),
                source=chunk.source,
                metadata={
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "module": chunk.module_name,
                    "table": chunk.table_name,
                    "procedure": chunk.procedure_name,
                    "business_object": chunk.business_object,
                    "issue_type": chunk.issue_type,
                    "tags": _safe_json(chunk.tags, []),
                    "approval_status": chunk.approval_status,
                    "confidence": float(chunk.confidence or 0),
                    "retriever": "sqlite-vector",
                },
            )
            for score, chunk in scored[: query.top_k]
        ]


class QdrantKnowledgeRetriever(KnowledgeRetriever):
    def __init__(self, fallback: KnowledgeRetriever | None = None):
        self.fallback = fallback or SQLiteKnowledgeRetriever()

    def index_document(self, db: Session, **kwargs) -> int:
        # Qdrant client integration is intentionally isolated here. The app can swap
        # this implementation in later without touching the investigation engine.
        return self.fallback.index_document(db, **kwargs)

    def retrieve(self, db: Session, query: KnowledgeQuery) -> list[RetrievedDocument]:
        return self.fallback.retrieve(db, query)


class PgVectorKnowledgeRetriever(KnowledgeRetriever):
    def __init__(self, fallback: KnowledgeRetriever | None = None):
        self.fallback = fallback or SQLiteKnowledgeRetriever()

    def index_document(self, db: Session, **kwargs) -> int:
        # pgvector-specific SQL belongs here when pgvector is enabled.
        return self.fallback.index_document(db, **kwargs)

    def retrieve(self, db: Session, query: KnowledgeQuery) -> list[RetrievedDocument]:
        return self.fallback.retrieve(db, query)


def get_knowledge_retriever(settings: Settings | None = None) -> KnowledgeRetriever:
    backend = (settings or Settings.from_env()).knowledge_retriever_backend
    if backend == "qdrant":
        return QdrantKnowledgeRetriever()
    if backend in {"pgvector", "postgres", "postgresql"}:
        return PgVectorKnowledgeRetriever()
    return SQLiteKnowledgeRetriever()


def retrieve_documents(db: Session, organization_id: str, workspace_id: str, question: str) -> list[RetrievedDocument]:
    retriever = get_knowledge_retriever()
    return retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=organization_id,
            workspace_id=workspace_id,
            question=question,
            top_k=8,
        ),
    )


def index_document_knowledge(
    db: Session,
    *,
    organization_id: str,
    workspace_id: str,
    document: DocumentModel,
    version: DocumentVersionModel,
) -> int:
    return get_knowledge_retriever().index_document(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        document=document,
        version=version,
    )


def index_approved_knowledge_article(db: Session, article: KnowledgeArticleModel) -> int:
    text = "\n".join(
        [
            article.title,
            article.symptoms,
            article.actual_root_cause,
            article.fix_summary,
            article.sql_changed,
            article.procedures_changed,
            article.test_cases,
            article.proof_of_fix,
            article.rollback_plan,
            article.body,
        ]
    )
    chunks = chunk_text(text) or [text or article.title]
    db.query(KnowledgeChunkModel).filter(
        KnowledgeChunkModel.organization_id == article.organization_id,
        KnowledgeChunkModel.workspace_id == article.workspace_id,
        KnowledgeChunkModel.source == "approved_knowledge",
        KnowledgeChunkModel.document_id.is_(None),
        KnowledgeChunkModel.source_title == article.title,
    ).delete(synchronize_session=False)
    for index, chunk in enumerate(chunks):
        db.add(
            KnowledgeChunkModel(
                organization_id=article.organization_id,
                workspace_id=article.workspace_id,
                document_id=None,
                document_version_id=None,
                source="approved_knowledge",
                source_title=article.title,
                chunk_index=index,
                content=chunk,
                embedding_json=json.dumps(embed_text(chunk)),
                module_name=article.module_name,
                table_name="",
                procedure_name=article.procedures_changed,
                business_object=article.module_name,
                issue_type=article.issue_type,
                tags=json.dumps(tokenize(article.detected_entities)[:20]),
                approval_status="approved",
                confidence=article.confidence_after_approval,
            )
        )
    article.indexed_at = _utc_now()
    return len(chunks)


def keyword_fallback_retrieve(db: Session, query: KnowledgeQuery) -> list[RetrievedDocument]:
    documents = (
        db.query(DocumentModel, DocumentVersionModel)
        .join(DocumentVersionModel, DocumentVersionModel.document_id == DocumentModel.id)
        .filter(
            DocumentModel.organization_id == query.organization_id,
            DocumentModel.workspace_id == query.workspace_id,
            DocumentModel.is_deleted.is_(False),
        )
        .order_by(DocumentModel.title.asc())
        .all()
    )
    tokens = set(tokenize(query.question))
    results: list[RetrievedDocument] = []
    for document, version in documents:
        text = extract_text(Path(version.storage_key), version.mime_type)
        snippet = "Uploaded document available; vector index unavailable, keyword fallback used."
        if text:
            matching_lines = [line.strip() for line in text.splitlines() if any(token in line.lower() for token in tokens)]
            snippet = "\n".join(matching_lines[:3]) or text[:500]
        score = len(tokens & set(tokenize(f"{document.title} {snippet}"))) / max(1, len(tokens))
        results.append(
            RetrievedDocument(
                title=document.title,
                filename=version.filename,
                snippet=snippet,
                score=round(score, 4),
                source="keyword-fallback",
                metadata={"retriever": "keyword-fallback", "document_id": document.id},
            )
        )
    results.sort(key=lambda item: item.score, reverse=True)
    return results[: query.top_k]


def extract_text(path: Path, mime_type: str = "") -> str:
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".sql", ".csv"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        return _extract_docx_text(path)
    if suffix == ".pdf":
        # Best-effort only. Full PDF extraction needs a dedicated parser.
        data = path.read_bytes()
        text = data.decode("latin-1", errors="ignore")
        return "\n".join(re.findall(r"[A-Za-z0-9_.,:;() /\\-]{20,}", text))[:10000]
    return path.read_text(encoding="utf-8", errors="ignore") if "text" in mime_type else ""


def chunk_text(text: str, max_tokens: int = 180, overlap: int = 35) -> list[str]:
    words = re.findall(r"\S+", text)
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, max_tokens - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + max_tokens]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks[:500]


def embed_text(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))


def tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9_/-]{3,}", text.lower())]


def infer_metadata(title: str, text: str) -> dict[str, Any]:
    combined = f"{title}\n{text}"
    procedures = re.findall(r"\bsp_[a-zA-Z0-9_]+\b", combined)
    tables = re.findall(r"`([a-zA-Z][a-zA-Z0-9_]*)`", combined)
    issue_terms = [term for term in ("duplicate", "missing", "slow", "timeout", "failed", "deadlock", "blocking", "mismatch") if term in combined.lower()]
    tags = sorted(set(issue_terms + [proc.lower() for proc in procedures[:5]]))
    return {
        "module": _first_heading_value(combined, "module"),
        "table": tables[0] if tables else "",
        "procedure": procedures[0] if procedures else "",
        "business_object": _first_heading_value(combined, "business object"),
        "issue_type": issue_terms[0] if issue_terms else "",
        "tags": tags,
    }


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return ""
    xml = re.sub(r"<w:tab\s*/>", "\t", xml)
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def _first_heading_value(text: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}\s*[:=-]\s*([A-Za-z0-9_/-]+)", text, re.I)
    return match.group(1)[:120] if match else ""


def _loads_vector(value: str) -> list[float]:
    try:
        parsed = json.loads(value or "[]")
        return [float(item) for item in parsed]
    except Exception:
        return []


def _safe_json(value: str, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return default


def _filter_column(field_name: str):
    return {
        "workspace": KnowledgeChunkModel.workspace_id,
        "document": KnowledgeChunkModel.document_id,
        "module": KnowledgeChunkModel.module_name,
        "table": KnowledgeChunkModel.table_name,
        "procedure": KnowledgeChunkModel.procedure_name,
        "business_object": KnowledgeChunkModel.business_object,
        "issue_type": KnowledgeChunkModel.issue_type,
        "source": KnowledgeChunkModel.source,
        "approval_status": KnowledgeChunkModel.approval_status,
    }.get(field_name)


def _metadata_score(question_tokens: set[str], chunk: KnowledgeChunkModel) -> float:
    metadata = " ".join(
        [
            chunk.module_name,
            chunk.table_name,
            chunk.procedure_name,
            chunk.business_object,
            chunk.issue_type,
            chunk.source_title,
            " ".join(_safe_json(chunk.tags, [])),
        ]
    )
    if not question_tokens:
        return 0.0
    return len(question_tokens & set(tokenize(metadata))) / len(question_tokens)


def _utc_now():
    from legacydb_copilot.common import utc_now

    return utc_now()
