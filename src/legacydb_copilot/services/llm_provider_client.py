from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import request

from sqlalchemy.orm import Session

from legacydb_copilot.services.llm_invocation_audit_service import (
    InvocationContext,
    LLMInvocationAuditService,
)


@dataclass(frozen=True)
class ProviderRequest:
    provider: str
    model: str
    endpoint: str
    api_key: str
    body: dict[str, Any]
    audit_payload: dict[str, Any] | None = None
    system_prompt: str = ""
    user_prompt: str = ""
    timeout_seconds: float = 30.0
    retry_attempt: int = 1
    will_retry_on_failure: bool = False
    prompt_template_name: str | None = None
    prompt_template_version: str | None = None
    input_cost_per_million: float = 0.0
    output_cost_per_million: float = 0.0


class AuditedLLMProviderClient:
    """The sole HTTP boundary for model, judge, and embedding provider requests."""

    def __init__(
        self,
        *,
        db: Session | None = None,
        context: InvocationContext | None = None,
    ):
        self.audit = LLMInvocationAuditService(db) if db is not None and context is not None else None
        self.context = context

    def invoke_json(self, provider_request: ProviderRequest) -> dict[str, Any]:
        audit_row = None
        if self.audit is not None and self.context is not None:
            audit_row = self.audit.start_invocation(
                context=self.context,
                provider=provider_request.provider,
                model_name=provider_request.model,
                system_prompt=provider_request.system_prompt,
                user_prompt=provider_request.user_prompt,
                request_payload=provider_request.audit_payload or provider_request.body,
                request_parameters=provider_request.body,
                retry_attempt=provider_request.retry_attempt,
                prompt_template_name=provider_request.prompt_template_name,
                prompt_template_version=provider_request.prompt_template_version,
            )
        call = request.Request(
            provider_request.endpoint,
            data=json.dumps(provider_request.body, default=str).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {provider_request.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(call, timeout=provider_request.timeout_seconds) as response:
                response_json = json.loads(response.read().decode("utf-8"))
            if self.audit is not None:
                self.audit.complete_invocation(
                    audit_row,
                    response_json,
                    input_cost_per_million=provider_request.input_cost_per_million,
                    output_cost_per_million=provider_request.output_cost_per_million,
                )
            return response_json
        except Exception as exc:
            if self.audit is not None:
                self.audit.fail_invocation(
                    audit_row,
                    exc,
                    was_retried=provider_request.will_retry_on_failure,
                )
            raise
