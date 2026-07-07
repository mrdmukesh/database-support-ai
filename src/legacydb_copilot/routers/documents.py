from __future__ import annotations

from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.common import DomainError
from legacydb_copilot.config import Settings
from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.db.models import DocumentModel, DocumentVersionModel, WorkspaceMembershipModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.documents import UploadPolicy, content_sha256, detect_mime_type
from legacydb_copilot.schemas import DocumentCreate, DocumentRead
from legacydb_copilot.security.access_control import require_workspace_access
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.rag_retrieval_service import index_document_knowledge
from legacydb_copilot.services.storage_service import get_app_storage

router = APIRouter(prefix="/documents", tags=["documents"])
LOCAL_DOCUMENT_ROOT = Path("storage/documents")


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("documents:manage")),
) -> DocumentModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles create document within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        HTTP request -> auth/RBAC -> service call -> persistence/audit -> response.
    
    Safety considerations:
        Document indexing must remain workspace-scoped and must not index unapproved live database rows.
    """
    assert_same_organization(current_user, payload.organization_id)
    require_workspace_access(db, current_user, payload.workspace_id, action="upload")
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
        record_audit_event(
            db,
            organization_id=document.organization_id,
            workspace_id=document.workspace_id,
            user_id=current_user.id,
            action="document.create",
            resource_type="document",
            resource_id=document.id,
            metadata={"title": document.title, "filename": payload.filename},
        )
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Uploads a workspace document, stores the file, records document metadata, and indexes it for retrieval.

    Input:
        Organization/workspace/title form fields, uploaded file bytes, current user, and app database session.

    Output:
        DocumentModel with latest version metadata.

    Called by:
        Documents page when a user uploads runbooks, known issues, procedures, or business process notes.

    Flow:
        Upload -> MIME/size validation -> app storage -> document/version row -> RAG indexing -> audit log.

    Safety:
        Upload is workspace-scoped, validates allowed file types/sizes, and indexes documents only inside the same
        workspace knowledge boundary.
    """

    assert_same_organization(current_user, organization_id)
    require_workspace_access(db, current_user, workspace_id, action="upload")
    filename = Path(file.filename or "").name
    content = await file.read()
    try:
        UploadPolicy().validate(filename, len(content))
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sha256 = content_sha256(content)
    mime_type = file.content_type or detect_mime_type(filename)
    storage_key = (
        LOCAL_DOCUMENT_ROOT
        / organization_id
        / workspace_id
        / f"{sha256}-{filename}"
    ).as_posix()
    get_app_storage().save_bytes(storage_key, content, mime_type)

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
        record_audit_event(
            db,
            organization_id=document.organization_id,
            workspace_id=document.workspace_id,
            user_id=current_user.id,
            action="document.upload",
            resource_type="document",
            resource_id=document.id,
            metadata={"title": document.title, "filename": filename, "size_bytes": len(content)},
        )
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles list documents within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        HTTP request -> auth/RBAC -> service call -> persistence/audit -> response.
    
    Safety considerations:
        Document indexing must remain workspace-scoped and must not index unapproved live database rows.
    """
    assert_same_organization(current_user, organization_id)
    query = db.query(DocumentModel).filter(
        DocumentModel.organization_id == organization_id,
        DocumentModel.is_deleted.is_(False),
    )
    if workspace_id:
        require_workspace_access(db, current_user, workspace_id, action="read")
        query = query.filter(DocumentModel.workspace_id == workspace_id)
    elif Settings.from_env().feature_enterprise_rbac_enabled:
        workspace_ids = [
            item.workspace_id
            for item in db.query(WorkspaceMembershipModel.workspace_id)
            .filter(
                WorkspaceMembershipModel.user_id == current_user.id,
                WorkspaceMembershipModel.is_active.is_(True),
            )
            .all()
        ]
        query = query.filter(DocumentModel.workspace_id.in_(workspace_ids or [""]))
    return list(query.order_by(DocumentModel.created_at.desc()).all())
