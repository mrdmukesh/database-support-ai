from __future__ import annotations

from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.common import DomainError
from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.db.models import DocumentModel, DocumentVersionModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.documents import UploadPolicy, content_sha256, detect_mime_type
from legacydb_copilot.schemas import DocumentCreate, DocumentRead
from legacydb_copilot.services.rag_retrieval_service import index_document_knowledge

router = APIRouter(prefix="/documents", tags=["documents"])
LOCAL_DOCUMENT_ROOT = Path("storage/documents")


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("documents:manage")),
) -> DocumentModel:
    assert_same_organization(current_user, payload.organization_id)
    try:
        UploadPolicy().validate(payload.filename, payload.size_bytes)
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    document = DocumentModel(
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
        owner_id=payload.owner_id,
        title=payload.title,
    )
    db.add(document)
    try:
        db.flush()
        version = DocumentVersionModel(
            document_id=document.id,
            version=1,
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            sha256=payload.sha256,
            storage_key=payload.storage_key,
        )
        db.add(version)
        db.flush()
        try:
            index_document_knowledge(
                db,
                organization_id=payload.organization_id,
                workspace_id=payload.workspace_id,
                document=document,
                version=version,
            )
        except Exception:
            pass
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document could not be created") from exc
    db.refresh(document)
    return document


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    organization_id: Annotated[str, Form()],
    workspace_id: Annotated[str, Form()],
    title: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("documents:manage")),
) -> DocumentModel:
    assert_same_organization(current_user, organization_id)
    filename = Path(file.filename or "").name
    content = await file.read()
    try:
        UploadPolicy().validate(filename, len(content))
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sha256 = content_sha256(content)
    mime_type = file.content_type or detect_mime_type(filename)
    document_dir = LOCAL_DOCUMENT_ROOT / organization_id / workspace_id
    document_dir.mkdir(parents=True, exist_ok=True)
    storage_path = document_dir / f"{sha256}-{filename}"
    storage_path.write_bytes(content)
    storage_key = storage_path.as_posix()

    document = DocumentModel(
        organization_id=organization_id,
        workspace_id=workspace_id,
        owner_id=current_user.id,
        title=title,
    )
    db.add(document)
    try:
        db.flush()
        version = DocumentVersionModel(
            document_id=document.id,
            version=1,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=sha256,
            storage_key=storage_key,
        )
        db.add(version)
        db.flush()
        try:
            index_document_knowledge(
                db,
                organization_id=organization_id,
                workspace_id=workspace_id,
                document=document,
                version=version,
            )
        except Exception:
            pass
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document could not be uploaded") from exc
    db.refresh(document)
    return document


@router.get("", response_model=list[DocumentRead])
def list_documents(
    organization_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("documents:read")),
    workspace_id: str | None = None,
) -> list[DocumentModel]:
    assert_same_organization(current_user, organization_id)
    query = db.query(DocumentModel).filter(
        DocumentModel.organization_id == organization_id,
        DocumentModel.is_deleted.is_(False),
    )
    if workspace_id:
        query = query.filter(DocumentModel.workspace_id == workspace_id)
    return list(query.order_by(DocumentModel.created_at.desc()).all())
