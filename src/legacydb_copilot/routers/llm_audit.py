from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from legacydb_copilot.db.models import InvestigationModel, LLMInvocationAuditModel, UserModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.llm_invocation_audit_service import LLMInvocationAuditService

router = APIRouter(prefix="/admin", tags=["llm-invocation-audit"])
AuditAdmin = Annotated[UserModel, Depends(require_permission("admin.llm_audit.read"))]


def _scope(user: UserModel) -> str | None:
    return None if user.role == "super_admin" else user.organization_id


def _summary(row: LLMInvocationAuditModel) -> dict:
    return {
        "llm_invocation_id": row.id,
        "investigation_id": row.investigation_id,
        "investigation_run_id": row.investigation_run_id,
        "workspace_id": row.workspace_id,
        "organization_id": row.organization_id,
        "user_id": row.user_id,
        "stage_name": row.stage_name,
        "agent_name": row.agent_name,
        "provider": row.provider,
        "model_name": row.model_name,
        "status": row.status,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "total_tokens": row.total_tokens,
        "duration_ms": row.duration_ms,
        "estimated_cost": float(row.estimated_cost) if row.estimated_cost is not None else None,
        "currency": row.currency,
        "retry_attempt": row.retry_attempt,
        "logical_request_id": row.logical_request_id,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
    }


def _detail(row: LLMInvocationAuditModel) -> dict:
    data = _summary(row)
    data.update({
        "session_id": row.session_id, "correlation_id": row.correlation_id,
        "trace_id": row.trace_id, "parent_span_id": row.parent_span_id,
        "step_number": row.step_number, "model_version": row.model_version,
        "temperature": float(row.temperature) if row.temperature is not None else None,
        "max_tokens": row.max_tokens, "response_format": row.response_format,
        "tool_choice": row.tool_choice,
        "system_prompt_sanitized": row.system_prompt_sanitized,
        "user_prompt_sanitized": row.user_prompt_sanitized,
        "context_payload_sanitized": row.context_payload_sanitized,
        "tool_definitions_sanitized": row.tool_definitions_sanitized,
        "request_payload_hash": row.request_payload_hash,
        "response_text_sanitized": row.response_text_sanitized,
        "response_payload_hash": row.response_payload_hash,
        "cached_tokens": row.cached_tokens, "reasoning_tokens": row.reasoning_tokens,
        "finish_reason": row.finish_reason, "error_code": row.error_code,
        "error_message_sanitized": row.error_message_sanitized,
        "was_retried": row.was_retried, "fallback_from_model": row.fallback_from_model,
        "fallback_reason": row.fallback_reason,
        "prompt_template_name": row.prompt_template_name,
        "prompt_template_version": row.prompt_template_version,
        "prompt_template_hash": row.prompt_template_hash,
        "application_commit": row.application_commit,
        "application_version": row.application_version,
        "redaction_notice": "Sensitive values have been redacted.",
    })
    return data


@router.get("/llm-invocations")
def search_llm_invocations(
    user: AuditAdmin,
    db: Session = Depends(get_db_session),
    investigation_id: str | None = None,
    workspace_id: str | None = None,
    status: str | None = None,
    stage_name: str | None = None,
    agent_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    user_id: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    min_duration_ms: int | None = Query(default=None, ge=0),
    failed_only: bool = False,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict:
    rows, total = LLMInvocationAuditService(db).search_invocations(
        organization_id=_scope(user), workspace_id=workspace_id, investigation_id=investigation_id,
        status=status, stage_name=stage_name, agent_name=agent_name, provider=provider,
        model=model, user_id=user_id, started_after=started_after, started_before=started_before,
        min_duration_ms=min_duration_ms, failed_only=failed_only, search=search,
        page=page, page_size=page_size,
    )
    return {"items": [_summary(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.get("/investigations/{investigation_id}/llm-invocations")
def investigation_llm_invocations(
    investigation_id: str, user: AuditAdmin, db: Session = Depends(get_db_session)
) -> dict:
    investigation = db.get(InvestigationModel, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if _scope(user) is not None and investigation.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Investigation access denied")
    rows = LLMInvocationAuditService(db).get_invocations_for_investigation(
        investigation_id, organization_id=_scope(user)
    )
    return {
        "items": [_summary(row) for row in rows],
        "captured": bool(rows),
        "message": None if rows else "LLM invocation audit data was not captured for this investigation.",
    }


@router.get("/llm-invocations/{invocation_id}")
def llm_invocation_detail(
    invocation_id: str, user: AuditAdmin, db: Session = Depends(get_db_session)
) -> dict:
    row = LLMInvocationAuditService(db).get_invocation_detail(invocation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="LLM invocation not found")
    if _scope(user) is not None and row.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="LLM invocation access denied")
    record_audit_event(
        db, organization_id=row.organization_id, workspace_id=row.workspace_id, user_id=user.id,
        action="LLM_AUDIT_DETAIL_VIEWED", resource_type="llm_invocation", resource_id=row.id,
        metadata={"investigation_id": row.investigation_id},
    )
    return _detail(row)
