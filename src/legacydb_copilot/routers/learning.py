from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
import json

from legacydb_copilot.db.base import utc_now
from legacydb_copilot.db.models import (
    InvestigationFeedbackModel,
    InvestigationModel,
    KnowledgeArticleModel,
)
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.security.access_control import require_resource_owner_workspace, require_workspace_access
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.schemas import (
    FeedbackApprovalRequest,
    InvestigationFeedbackCreate,
    InvestigationFeedbackRead,
    InvestigationRead,
    InvestigationStatus,
    KnowledgeArticleRead,
    LearningDashboardRead,
)
from legacydb_copilot.services.rag_retrieval_service import index_approved_knowledge_article
from legacydb_copilot.services.report_generator import REPORT_HISTORY_DIR, report_file_stem
from legacydb_copilot.services.report_snapshot_service import report_from_dict

router = APIRouter(prefix="/learning", tags=["learning"])


def _get_investigation(db: Session, investigation_id: str) -> InvestigationModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for get investigation within learning.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in learning.py.
    
    Where it fits in the flow:
        Investigation -> feedback -> pending approval -> approved knowledge -> indexing.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    investigation = db.get(InvestigationModel, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation


def _report_links_for_investigation(investigation: InvestigationModel) -> dict[str, str] | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for report links for investigation within learning.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in learning.py.
    
    Where it fits in the flow:
        Investigation -> feedback -> pending approval -> approved knowledge -> indexing.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    try:
        storage_refs = json.loads(investigation.report_storage_json or "{}")
    except (TypeError, json.JSONDecodeError):
        storage_refs = {}
    if storage_refs:
        by_extension = {
            Path(filename).suffix.lower(): filename
            for filename in storage_refs
            if Path(filename).suffix.lower() in {".html", ".pdf", ".docx", ".xlsx"}
            and "_executive_rca" in filename
        }
        if {".html", ".pdf", ".docx", ".xlsx"}.issubset(by_extension):
            base = f"/reports/{investigation.id}"
            return {
                "investigation_id": investigation.id,
                **{ext.lstrip("."): f"{base}/{filename}" for ext, filename in by_extension.items()},
            }
    if not investigation.report_snapshot_json:
        report_dir = (REPORT_HISTORY_DIR / investigation.id).resolve()
        history_root = REPORT_HISTORY_DIR.resolve()
        if report_dir.exists() and (report_dir == history_root or history_root in report_dir.parents):
            by_extension = {path.suffix.lower(): path.name for path in report_dir.iterdir() if path.is_file()}
            if {".html", ".pdf", ".docx", ".xlsx"}.issubset(by_extension):
                base = f"/reports/{investigation.id}"
                return {
                    "investigation_id": investigation.id,
                    "html": f"{base}/{by_extension['.html']}",
                    "pdf": f"{base}/{by_extension['.pdf']}",
                    "docx": f"{base}/{by_extension['.docx']}",
                    "xlsx": f"{base}/{by_extension['.xlsx']}",
                }
        return None
    try:
        report = report_from_dict(json.loads(investigation.report_snapshot_json))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    stem = f"{report_file_stem(report)}_executive_rca"
    base = f"/reports/{investigation.id}"
    return {
        "investigation_id": investigation.id,
        "html": f"{base}/{stem}.html",
        "pdf": f"{base}/{stem}.pdf",
        "docx": f"{base}/{stem}.docx",
        "xlsx": f"{base}/{stem}.xlsx",
    }


@router.get("/dashboard", response_model=LearningDashboardRead)
def learning_dashboard(
    organization_id: str,
    workspace_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("learning:read")),
) -> dict[str, object]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles learning dashboard within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Investigation -> feedback -> pending approval -> approved knowledge -> indexing.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    assert_same_organization(current_user, organization_id)
    require_workspace_access(db, current_user, workspace_id, action="read")
    filters = (
        InvestigationModel.organization_id == organization_id,
        InvestigationModel.workspace_id == workspace_id,
    )
    reminder_cutoff = utc_now() - timedelta(hours=24)
    reminders = (
        db.query(InvestigationModel)
        .filter(
            *filters,
            InvestigationModel.status.in_(
                [InvestigationStatus.OPEN.value, InvestigationStatus.AI_ANSWERED.value]
            ),
            InvestigationModel.created_at <= reminder_cutoff,
        )
        .order_by(InvestigationModel.created_at.asc())
        .limit(10)
        .all()
    )
    return {
        "open_investigations": db.query(func.count(InvestigationModel.id))
        .filter(*filters, InvestigationModel.status.in_([InvestigationStatus.OPEN.value, InvestigationStatus.AI_ANSWERED.value]))
        .scalar()
        or 0,
        "pending_feedback": db.query(func.count(InvestigationModel.id))
        .filter(*filters, InvestigationModel.status == InvestigationStatus.DEVELOPER_REVIEW.value)
        .scalar()
        or 0,
        "pending_approval": db.query(func.count(InvestigationFeedbackModel.id))
        .filter(
            InvestigationFeedbackModel.organization_id == organization_id,
            InvestigationFeedbackModel.workspace_id == workspace_id,
            InvestigationFeedbackModel.status == InvestigationStatus.PENDING_APPROVAL.value,
        )
        .scalar()
        or 0,
        "approved_knowledge": db.query(func.count(KnowledgeArticleModel.id))
        .filter(
            KnowledgeArticleModel.organization_id == organization_id,
            KnowledgeArticleModel.workspace_id == workspace_id,
            KnowledgeArticleModel.is_active.is_(True),
        )
        .scalar()
        or 0,
        "reminders": reminders,
    }


@router.get("/investigations", response_model=list[InvestigationRead])
def list_investigations(
    organization_id: str,
    workspace_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("learning:read")),
    status_filter: str | None = None,
) -> list[InvestigationModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles list investigations within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Investigation -> feedback -> pending approval -> approved knowledge -> indexing.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    assert_same_organization(current_user, organization_id)
    require_workspace_access(db, current_user, workspace_id, action="read")
    query = db.query(InvestigationModel).filter(
        InvestigationModel.organization_id == organization_id,
        InvestigationModel.workspace_id == workspace_id,
    )
    if status_filter:
        query = query.filter(InvestigationModel.status == status_filter)
    return list(query.order_by(InvestigationModel.created_at.desc()).limit(100).all())


@router.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("learning:read")),
) -> dict[str, object]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles get investigation within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Investigation -> feedback -> pending approval -> approved knowledge -> indexing.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    investigation = _get_investigation(db, investigation_id)
    require_resource_owner_workspace(db, current_user, investigation, action="read")
    return {
        "id": investigation.id,
        "organization_id": investigation.organization_id,
        "workspace_id": investigation.workspace_id,
        "connection_id": investigation.connection_id,
        "connection_name": investigation.connection_name,
        "user_question": investigation.user_question,
        "detected_intent": investigation.detected_intent,
        "ai_answer": investigation.ai_answer,
        "confidence_score": float(investigation.confidence_score or 0),
        "report_path": investigation.report_path,
        "status": investigation.status,
        "created_at": investigation.created_at,
        "report": _report_links_for_investigation(investigation),
    }


@router.post(
    "/investigations/{investigation_id}/feedback",
    response_model=InvestigationFeedbackRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    investigation_id: str,
    payload: InvestigationFeedbackCreate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("learning:feedback")),
) -> InvestigationFeedbackModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Captures developer feedback after an investigation without directly teaching the knowledge base.

    Input:
        Investigation id, feedback details, actual root cause/fix/test evidence, current user, and app DB session.

    Output:
        InvestigationFeedbackModel with PENDING_APPROVAL status.

    Called by:
        Human-approved Learning Loop UI when a user reviews an AI answer later or immediately after an incident.

    Flow:
        Investigation -> developer feedback -> pending approval -> DBA/Admin review -> approved knowledge indexing.

    Safety:
        Feedback is not added to RAG until a human approver explicitly approves it.
    """

    investigation = _get_investigation(db, investigation_id)
    require_resource_owner_workspace(db, current_user, investigation, action="write")
    feedback = InvestigationFeedbackModel(
        organization_id=investigation.organization_id,
        workspace_id=investigation.workspace_id,
        investigation_id=investigation.id,
        submitted_by_id=current_user.id,
        rating=payload.rating.value,
        actual_root_cause=payload.actual_root_cause,
        actual_fix_applied=payload.actual_fix_applied,
        sql_or_procedure_changed=payload.sql_or_procedure_changed,
        test_cases_executed=payload.test_cases_executed,
        proof_of_fix=payload.proof_of_fix,
        rollback_used=payload.rollback_used,
        production_issue_resolved=payload.production_issue_resolved,
        notes=payload.notes,
        status=InvestigationStatus.PENDING_APPROVAL.value,
    )
    investigation.status = InvestigationStatus.PENDING_APPROVAL.value
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/feedback", response_model=list[InvestigationFeedbackRead])
def list_feedback(
    organization_id: str,
    workspace_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("learning:read")),
    status_filter: str | None = None,
) -> list[InvestigationFeedbackModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles list feedback within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Investigation -> feedback -> pending approval -> approved knowledge -> indexing.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    assert_same_organization(current_user, organization_id)
    require_workspace_access(db, current_user, workspace_id, action="read")
    query = db.query(InvestigationFeedbackModel).filter(
        InvestigationFeedbackModel.organization_id == organization_id,
        InvestigationFeedbackModel.workspace_id == workspace_id,
    )
    if status_filter:
        query = query.filter(InvestigationFeedbackModel.status == status_filter)
    return list(query.order_by(InvestigationFeedbackModel.created_at.desc()).limit(100).all())


@router.post("/feedback/{feedback_id}/review", response_model=InvestigationFeedbackRead)
def review_feedback(
    feedback_id: str,
    payload: FeedbackApprovalRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("learning:approve")),
) -> InvestigationFeedbackModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Approves or rejects submitted investigation feedback and creates reusable approved knowledge only on approval.

    Input:
        Feedback id, approval payload, current DBA/Admin user, and app DB session.

    Output:
        Updated InvestigationFeedbackModel and optional KnowledgeArticleModel.

    Called by:
        Learning review page for DBA/Lead/Admin approval.

    Flow:
        Pending feedback -> approval/rejection -> audit event -> approved knowledge article -> RAG indexing.

    Safety:
        The app never learns from unapproved feedback. Rejections are retained for audit but not indexed.
    """

    feedback = db.get(InvestigationFeedbackModel, feedback_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    require_resource_owner_workspace(db, current_user, feedback, action="approve")
    investigation = _get_investigation(db, feedback.investigation_id)
    feedback.reviewed_by_id = current_user.id
    feedback.reviewed_at = utc_now()
    feedback.review_notes = payload.review_notes

    if not payload.approved:
        feedback.status = InvestigationStatus.REJECTED.value
        investigation.status = InvestigationStatus.REJECTED.value
        record_audit_event(
            db,
            organization_id=feedback.organization_id,
            workspace_id=feedback.workspace_id,
            user_id=current_user.id,
            action="knowledge_approval.rejected",
            resource_type="investigation_feedback",
            resource_id=feedback.id,
            status="rejected",
            metadata={"investigation_id": investigation.id},
        )
        db.commit()
        db.refresh(feedback)
        return feedback

    article = KnowledgeArticleModel(
        organization_id=feedback.organization_id,
        workspace_id=feedback.workspace_id,
        incident_id=None,
        approved_by_id=current_user.id,
        title=payload.title or investigation.user_question[:240] or "Approved investigation fix",
        body=feedback.notes or feedback.actual_fix_applied or feedback.actual_root_cause,
        module_name=payload.module_name,
        issue_type=payload.issue_type or investigation.detected_intent,
        symptoms=investigation.user_question,
        detected_entities=investigation.extracted_entities_json,
        actual_root_cause=feedback.actual_root_cause,
        fix_summary=feedback.actual_fix_applied,
        sql_changed=feedback.sql_or_procedure_changed,
        procedures_changed=feedback.sql_or_procedure_changed,
        test_cases=feedback.test_cases_executed,
        proof_of_fix=feedback.proof_of_fix,
        rollback_plan=payload.rollback_plan or feedback.rollback_used,
        severity=payload.severity,
        confidence_after_approval=payload.confidence_after_approval,
        approved_at=utc_now(),
        source_investigation_id=investigation.id,
        is_active=True,
        indexed_at=utc_now(),
    )
    feedback.status = InvestigationStatus.APPROVED_KNOWLEDGE.value
    investigation.status = InvestigationStatus.APPROVED_KNOWLEDGE.value
    db.add(article)
    db.flush()
    record_audit_event(
        db,
        organization_id=feedback.organization_id,
        workspace_id=feedback.workspace_id,
        user_id=current_user.id,
        action="knowledge_approval.approved",
        resource_type="knowledge_article",
        resource_id=article.id,
        status="approved",
        metadata={"feedback_id": feedback.id, "investigation_id": investigation.id},
    )
    try:
        index_approved_knowledge_article(db, article)
    except Exception:
        pass
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/knowledge", response_model=list[KnowledgeArticleRead])
def list_knowledge(
    organization_id: str,
    workspace_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("learning:read")),
) -> list[KnowledgeArticleModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles list knowledge within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Investigation -> feedback -> pending approval -> approved knowledge -> indexing.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    assert_same_organization(current_user, organization_id)
    require_workspace_access(db, current_user, workspace_id, action="read")
    return list(
        db.query(KnowledgeArticleModel)
        .filter(
            KnowledgeArticleModel.organization_id == organization_id,
            KnowledgeArticleModel.workspace_id == workspace_id,
            KnowledgeArticleModel.is_active.is_(True),
        )
        .order_by(KnowledgeArticleModel.updated_at.desc())
        .limit(100)
        .all()
    )


@router.get("/similar-issues", response_model=list[KnowledgeArticleRead])
def similar_issues(
    organization_id: str,
    workspace_id: str,
    question: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("learning:read")),
) -> list[KnowledgeArticleModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles similar issues within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Investigation -> feedback -> pending approval -> approved knowledge -> indexing.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    from legacydb_copilot.services.approved_knowledge_service import search_approved_knowledge

    assert_same_organization(current_user, organization_id)
    require_workspace_access(db, current_user, workspace_id, action="read")
    return search_approved_knowledge(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        question=question,
        limit=10,
    )
