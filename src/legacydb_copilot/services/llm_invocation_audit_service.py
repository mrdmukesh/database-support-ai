from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import utc_now
from legacydb_copilot.db.models import LLMInvocationAuditModel
from legacydb_copilot.services.pii_masking_service import sanitize_ai_trace

logger = logging.getLogger(__name__)


class LLMStage(StrEnum):
    INTENT_ANALYSIS = "Intent Analysis"
    ENTITY_EXTRACTION = "Entity Extraction"
    METADATA_DISCOVERY = "Metadata Discovery"
    RELATIONSHIP_DISCOVERY = "Relationship Discovery"
    SAFE_SQL_PLANNING = "Safe SQL Planning"
    SQL_VALIDATION = "SQL Validation"
    EVIDENCE_COLLECTION = "Evidence Collection"
    EVIDENCE_VERIFICATION = "Evidence Verification"
    ROOT_CAUSE_REASONING = "Root Cause Reasoning"
    REPORT_COMPOSITION = "Report Composition"
    AI_JUDGE = "AI Judge"
    ANSWER_REFINEMENT = "Answer Refinement"


@dataclass(frozen=True)
class InvocationContext:
    organization_id: str
    workspace_id: str
    connection_id: str | None = None
    environment_type: str = "UNRESOLVED"
    policy_name: str = "UNRESOLVED_STRICT_READ_ONLY"
    policy_version: str = "v1"
    investigation_id: str | None = None
    investigation_run_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None
    parent_span_id: str | None = None
    agent_name: str = "reasoning_agent"
    stage_name: str = LLMStage.ROOT_CAUSE_REASONING
    step_number: int | None = 6
    logical_request_id: str | None = None


def payload_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _sanitized_json(value: Any) -> str:
    return json.dumps(sanitize_llm_audit_payload(value), ensure_ascii=False, default=str)


def sanitize_llm_audit_payload(value: Any) -> Any:
    """Apply the approved sanitizer and normalize placeholders for audit consumers."""
    sanitized = sanitize_ai_trace(value)
    if isinstance(sanitized, dict):
        protected: dict[str, Any] = {}
        for key, item in sanitized.items():
            if key.lower() in {"rows", "sample_rows", "sql_results", "result_payload"}:
                count = len(item) if isinstance(item, (list, tuple)) else None
                protected[key] = {
                    "redacted": "[REDACTED_PII]",
                    "row_count": count,
                }
            else:
                protected[key] = sanitize_llm_audit_payload(item)
        return protected
    if isinstance(sanitized, list):
        return [sanitize_llm_audit_payload(item) for item in sanitized]
    if not isinstance(sanitized, str):
        return sanitized
    replacements = {
        "[MASKED_SECRET]": "[REDACTED_SECRET]",
        "[MASKED_TOKEN]": "[REDACTED_TOKEN]",
        "[MASKED_CONNECTION_STRING]": "[REDACTED_CONNECTION_STRING]",
        "[MASKED_EMAIL]": "[REDACTED_PII]",
        "[MASKED_PHONE]": "[REDACTED_PII]",
        "[MASKED_IDENTIFIER]": "[REDACTED_PII]",
        "[MASKED_NAME]": "[REDACTED_PII]",
        "[MASKED_PII]": "[REDACTED_PII]",
    }
    for source, target in replacements.items():
        sanitized = sanitized.replace(source, target)
    return sanitized


def _sanitized_prompt(value: str) -> str:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return str(sanitize_llm_audit_payload(value))
    return json.dumps(sanitize_llm_audit_payload(parsed), ensure_ascii=False, default=str)


class LLMInvocationAuditService:
    """Best-effort internal writes and tenant-scoped read-only audit queries."""

    def __init__(self, db: Session):
        self.db = db

    def start_invocation(
        self,
        *,
        context: InvocationContext,
        provider: str,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        request_payload: Any,
        request_parameters: dict[str, Any],
        retry_attempt: int,
        prompt_template_name: str | None = None,
        prompt_template_version: str | None = None,
    ) -> LLMInvocationAuditModel | None:
        try:
            sanitized_request = sanitize_llm_audit_payload(request_payload)
            row = LLMInvocationAuditModel(
                investigation_id=context.investigation_id,
                investigation_run_id=context.investigation_run_id,
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                connection_id=context.connection_id,
                environment_type=context.environment_type,
                policy_name=context.policy_name,
                policy_version=context.policy_version,
                user_id=context.user_id,
                session_id=context.session_id,
                logical_request_id=context.logical_request_id or str(uuid4()),
                correlation_id=context.correlation_id,
                trace_id=context.trace_id,
                parent_span_id=context.parent_span_id,
                agent_name=context.agent_name,
                stage_name=str(context.stage_name),
                step_number=context.step_number,
                provider=provider,
                model_name=model_name,
                temperature=request_parameters.get("temperature"),
                max_tokens=request_parameters.get("max_output_tokens") or request_parameters.get("max_tokens"),
                response_format=request_parameters.get("response_format"),
                tool_choice=request_parameters.get("tool_choice"),
                system_prompt_sanitized=_sanitized_prompt(system_prompt),
                user_prompt_sanitized=_sanitized_prompt(user_prompt),
                context_payload_sanitized=_sanitized_json(sanitized_request),
                tool_definitions_sanitized=_sanitized_json(request_parameters.get("tools", [])),
                request_payload_hash=payload_hash(request_payload),
                started_at=utc_now(),
                status="started",
                retry_attempt=retry_attempt,
                prompt_template_name=prompt_template_name,
                prompt_template_version=prompt_template_version,
                prompt_template_hash=payload_hash(system_prompt) if prompt_template_name else None,
                application_commit=os.getenv("APPLICATION_COMMIT"),
                application_version=os.getenv("APPLICATION_VERSION"),
            )
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
            return row
        except Exception as exc:  # audit must never break the provider request
            logger.warning("LLM audit start failed (%s)", type(exc).__name__)
            return None

    def complete_invocation(
        self,
        row: LLMInvocationAuditModel | None,
        response: Any,
        *,
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
    ) -> None:
        if row is None:
            return
        try:
            completed = utc_now()
            usage = response.get("usage", {}) if isinstance(response, dict) else {}
            output = response.get("output_text") if isinstance(response, dict) else response
            input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
            with self.db.begin_nested():
                row.response_text_sanitized = _sanitized_json(output or response)
                row.response_payload_hash = payload_hash(response)
                row.prompt_tokens = input_tokens
                row.completion_tokens = output_tokens
                row.total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
                row.cached_tokens = int((usage.get("input_tokens_details") or {}).get("cached_tokens") or 0)
                row.reasoning_tokens = int((usage.get("output_tokens_details") or {}).get("reasoning_tokens") or 0)
                row.estimated_cost = (
                    input_tokens * input_cost_per_million
                    + output_tokens * output_cost_per_million
                ) / 1_000_000
                row.provider_request_id = str(response.get("id") or "") or None
                row.completed_at = completed
                row.duration_ms = int((completed - row.started_at).total_seconds() * 1000)
                row.status = "completed"
                row.finish_reason = _finish_reason(response)
                self.db.add(row)
        except Exception as exc:
            logger.warning("LLM audit completion failed (%s)", type(exc).__name__)

    def fail_invocation(self, row: LLMInvocationAuditModel | None, exc: Exception, *, was_retried: bool) -> None:
        if row is None:
            return
        try:
            completed = utc_now()
            status, code = _failure_status(exc)
            with self.db.begin_nested():
                row.completed_at = completed
                row.duration_ms = int((completed - row.started_at).total_seconds() * 1000)
                row.status = status
                row.error_code = code
                row.error_message_sanitized = str(sanitize_llm_audit_payload(str(exc)))
                row.was_retried = was_retried
                self.db.add(row)
        except Exception as audit_exc:
            logger.warning("LLM audit failure update failed (%s)", type(audit_exc).__name__)

    def get_invocation_detail(self, invocation_id: str) -> LLMInvocationAuditModel | None:
        return self.db.get(LLMInvocationAuditModel, invocation_id)

    def search_invocations(
        self,
        *,
        organization_id: str | None,
        workspace_id: str | None = None,
        investigation_id: str | None = None,
        status: str | None = None,
        stage_name: str | None = None,
        agent_name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        user_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        min_duration_ms: int | None = None,
        failed_only: bool = False,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "started_at",
        sort_direction: str = "asc",
    ) -> tuple[list[LLMInvocationAuditModel], int]:
        query = self.db.query(LLMInvocationAuditModel)
        filters = {
            "organization_id": organization_id, "workspace_id": workspace_id,
            "investigation_id": investigation_id, "status": status, "stage_name": stage_name,
            "agent_name": agent_name, "provider": provider, "user_id": user_id,
        }
        for field, value in filters.items():
            if value:
                query = query.filter(getattr(LLMInvocationAuditModel, field) == value)
        if model:
            query = query.filter(LLMInvocationAuditModel.model_name == model)
        if started_after:
            query = query.filter(LLMInvocationAuditModel.started_at >= started_after)
        if started_before:
            query = query.filter(LLMInvocationAuditModel.started_at <= started_before)
        if min_duration_ms is not None:
            query = query.filter(LLMInvocationAuditModel.duration_ms >= min_duration_ms)
        if failed_only:
            query = query.filter(LLMInvocationAuditModel.status.in_(["failed", "timeout", "rate_limited"]))
        if search:
            term = f"%{search}%"
            query = query.filter(or_(
                LLMInvocationAuditModel.system_prompt_sanitized.ilike(term),
                LLMInvocationAuditModel.user_prompt_sanitized.ilike(term),
            ))
        total = query.count()
        sortable_columns = {
            "started_at": LLMInvocationAuditModel.started_at,
            "investigation_id": LLMInvocationAuditModel.investigation_id,
            "provider": LLMInvocationAuditModel.provider,
            "model": LLMInvocationAuditModel.model_name,
            "stage_name": LLMInvocationAuditModel.stage_name,
            "status": LLMInvocationAuditModel.status,
            "prompt_tokens": LLMInvocationAuditModel.prompt_tokens,
            "completion_tokens": LLMInvocationAuditModel.completion_tokens,
            "duration_ms": LLMInvocationAuditModel.duration_ms,
            "estimated_cost": LLMInvocationAuditModel.estimated_cost,
        }
        sort_column = sortable_columns.get(sort_by, LLMInvocationAuditModel.started_at)
        order = sort_column.asc() if sort_direction == "asc" else sort_column.desc()
        rows = query.order_by(order, LLMInvocationAuditModel.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return rows, total

    def get_invocations_for_investigation(
        self, investigation_id: str, *, organization_id: str | None
    ) -> list[LLMInvocationAuditModel]:
        rows, _ = self.search_invocations(
            organization_id=organization_id, investigation_id=investigation_id, page_size=100
        )
        return rows


def _finish_reason(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    if response.get("status"):
        return str(response["status"])
    output = response.get("output")
    if isinstance(output, list) and output and isinstance(output[-1], dict):
        return output[-1].get("status")
    return None


def _failure_status(exc: Exception) -> tuple[str, str]:
    code = str(getattr(exc, "code", "") or type(exc).__name__)
    lowered = f"{type(exc).__name__} {exc} {code}".lower()
    if "429" in lowered or "rate" in lowered:
        return "rate_limited", code
    if isinstance(exc, TimeoutError) or "timeout" in lowered or "timed out" in lowered:
        return "timeout", code
    if "cancel" in lowered:
        return "cancelled", code
    return "failed", code
