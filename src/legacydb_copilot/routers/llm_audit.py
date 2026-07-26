from __future__ import annotations

from datetime import datetime
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from legacydb_copilot.db.models import (
    DatabaseConnectionModel, InvestigationModel, LLMInvocationAuditModel, UserModel, WorkspaceModel,
)
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.llm_invocation_audit_service import LLMInvocationAuditService

router = APIRouter(prefix="/admin", tags=["llm-invocation-audit"])
AuditAdmin = Annotated[UserModel, Depends(require_permission("admin.llm_audit.read"))]


def _scope(user: UserModel) -> str | None:
    return None if user.role == "super_admin" else user.organization_id


def _summary(
    row: LLMInvocationAuditModel,
    workspace_names: dict[str, str] | None = None,
    database_names: dict[str, str] | None = None,
) -> dict:
    prompt = " ".join(
        str(row.user_prompt_sanitized or row.system_prompt_sanitized or "").split()
    )
    prompt_preview = prompt[:180] + ("…" if len(prompt) > 180 else "")
    return {
        "llm_invocation_id": row.id,
        "investigation_id": row.investigation_id,
        "investigation_run_id": row.investigation_run_id,
        "workspace_id": row.workspace_id,
        "workspace_name": (workspace_names or {}).get(row.workspace_id or ""),
        "connection_id": row.connection_id,
        "database_name": (database_names or {}).get(row.connection_id or ""),
        "environment_type": row.environment_type,
        "policy_name": row.policy_name,
        "policy_version": row.policy_version,
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
        "provider_request_id": row.provider_request_id,
        "prompt_preview": prompt_preview,
        "reason": row.error_message_sanitized or row.error_code,
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


def _zero_invocation_explanation(investigation: InvestigationModel | None) -> dict | None:
    if investigation is None:
        return None
    outcome = investigation.llm_audit_outcome
    reason = investigation.llm_audit_reason
    if not outcome:
        try:
            trace = json.loads(investigation.ai_debug_trace_json or "{}")
        except (TypeError, ValueError):
            trace = {}
        if trace.get("ai_reasoning_invoked"):
            outcome, reason = "AUDIT_NOT_CAPTURED", "A provider call predates invocation audit capture."
        elif investigation.status == "AI_SKIPPED_BY_EVIDENCE_GATE":
            outcome = "AI_SKIPPED_BY_EVIDENCE_GATE"
            reason = str(trace.get("ai_skip_reason") or "The evidence gate did not permit LLM reasoning.")
        else:
            outcome, reason = "DETERMINISTIC_ONLY", "The investigation completed without a provider request."
    return {"code": outcome, "reason": reason}


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
    sort_by: Literal[
        "started_at", "investigation_id", "provider", "model", "stage_name",
        "status", "prompt_tokens", "completion_tokens", "duration_ms", "estimated_cost",
    ] = "started_at",
    sort_direction: Literal["asc", "desc"] = "desc",
) -> dict:
    rows, total = LLMInvocationAuditService(db).search_invocations(
        organization_id=_scope(user), workspace_id=workspace_id, investigation_id=investigation_id,
        status=status, stage_name=stage_name, agent_name=agent_name, provider=provider,
        model=model, user_id=user_id, started_after=started_after, started_before=started_before,
        min_duration_ms=min_duration_ms, failed_only=failed_only, search=search,
        page=page, page_size=page_size, sort_by=sort_by, sort_direction=sort_direction,
    )
    explanation = None
    if investigation_id and not rows:
        investigation = db.get(InvestigationModel, investigation_id)
        if investigation and (_scope(user) is None or investigation.organization_id == user.organization_id):
            explanation = _zero_invocation_explanation(investigation)
    total_pages = (total + page_size - 1) // page_size if total else 0
    workspace_ids = {row.workspace_id for row in rows if row.workspace_id}
    connection_ids = {row.connection_id for row in rows if row.connection_id}
    workspace_names = dict(
        db.query(WorkspaceModel.id, WorkspaceModel.name).filter(WorkspaceModel.id.in_(workspace_ids)).all()
    ) if workspace_ids else {}
    database_names = dict(
        db.query(DatabaseConnectionModel.id, DatabaseConnectionModel.name).filter(
            DatabaseConnectionModel.id.in_(connection_ids)
        ).all()
    ) if connection_ids else {}
    return {
        "items": [_summary(row, workspace_names, database_names) for row in rows], "page": page, "page_size": page_size,
        "total": total, "total_items": total, "total_pages": total_pages,
        "has_previous": page > 1, "has_next": page < total_pages,
        "sort_by": sort_by, "sort_direction": sort_direction,
        "zero_invocation_explanation": explanation,
    }


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
        "message": None if rows else "No LLM provider request occurred for this investigation.",
        "zero_invocation_explanation": None if rows else _zero_invocation_explanation(investigation),
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
