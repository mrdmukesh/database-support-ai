from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.pii_masking_service import sanitize_ai_trace
from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.state import InvestigationState

_GROUNDING_RULES = """
Use only supplied persisted verified evidence and cite evidence IDs for factual claims.
Label inference and evidence gaps explicitly. Never invent records or missing values.
NULL is not a missing row; do not calculate age when DateOfBirth is NULL.
Do not claim root cause when the issue was not reproduced.
Do not present corrective action or proof of fix as verified without supporting evidence.
Inferred relationships are not database-enforced foreign keys.
Stored procedures were inspected only and were not executed.
Acknowledge inaccessible objects, incomplete metadata, and all evidence gaps.
""".strip()


def _not_cancelled() -> bool:
    return False


@dataclass(frozen=True)
class ProviderReasoningResponse:
    reasoning: dict[str, Any]
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0


class InvocationAudit(Protocol):
    def start(
        self,
        *,
        state: InvestigationState,
        system_prompt: str,
        user_prompt: str,
        prompt_hash: str,
        evidence_ids: tuple[str, ...],
    ) -> str | None: ...

    def complete(self, invocation_id: str, response: ProviderReasoningResponse) -> bool: ...

    def fail(self, invocation_id: str, exception: Exception) -> bool: ...


@dataclass(frozen=True)
class ReasoningAdapter:
    load_evidence: Callable[[tuple[str, ...]], list[EvidenceResult]]
    build_prompt: Callable[[InvestigationState, list[EvidenceResult]], tuple[str, str]]
    invoke: Callable[[str, str], ProviderReasoningResponse]
    audit: InvocationAudit
    persist: Callable[[InvestigationState, dict[str, Any]], bool]
    max_prompt_chars: int = 24_000
    is_cancelled: Callable[[], bool] = _not_cancelled

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        if not state["provider_call_required"]:
            return {}
        if state["cancel_requested"] or self.is_cancelled():
            return {"provider_call_required": False, "llm_skip_reason": "Cancellation requested."}
        evidence_ids = tuple(state["verified_evidence_ids"])
        evidence = self.load_evidence(evidence_ids)
        loaded_ids = {item.evidence_id for item in evidence}
        if loaded_ids != set(evidence_ids):
            raise OperationalNodeError(
                "VERIFIED_EVIDENCE_LOAD_FAILED",
                "The persisted verified evidence set could not be loaded exactly.",
            )
        system_prompt, user_prompt = self.build_prompt(state, evidence)
        system_prompt = str(sanitize_ai_trace(f"{system_prompt}\n\n{_GROUNDING_RULES}"))[
            : self.max_prompt_chars // 2
        ]
        user_prompt = str(sanitize_ai_trace(user_prompt))[: self.max_prompt_chars // 2]
        prompt_hash = hashlib.sha256(f"{system_prompt}\n{user_prompt}".encode()).hexdigest()
        invocation_id = self.audit.start(
            state=state,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_hash=prompt_hash,
            evidence_ids=evidence_ids,
        )
        if not invocation_id:
            raise OperationalNodeError(
                "LLM_AUDIT_START_FAILED",
                "Provider invocation was blocked because its audit record could not be created.",
            )
        try:
            response = self.invoke(system_prompt, user_prompt)
        except Exception as exc:
            audited = self.audit.fail(invocation_id, exc)
            return {
                "llm_invocation_ids": [*state["llm_invocation_ids"], invocation_id],
                "ai_reasoning_invoked": True,
                "llm_audit_complete": audited,
                "provider_call_required": False,
                "reasoning_result": None,
                "reasoning_persisted": False,
                "deterministic_fallback_reason": f"Provider failure: {type(exc).__name__}.",
                "llm_skip_reason": "Provider failed; deterministic evidence summary required.",
            }
        if state["cancel_requested"] or self.is_cancelled():
            self.audit.fail(invocation_id, RuntimeError("cancelled"))
            return {"provider_call_required": False, "llm_skip_reason": "Cancellation requested."}
        audit_complete = self.audit.complete(invocation_id, response)
        if not audit_complete:
            raise OperationalNodeError(
                "LLM_AUDIT_COMPLETION_FAILED",
                "Provider response audit could not be completed.",
                context={"invocation_id": invocation_id},
            )
        reasoning = sanitize_ai_trace(response.reasoning)
        if not isinstance(reasoning, dict) or not self.persist(state, reasoning):
            raise OperationalNodeError(
                "REASONING_PERSISTENCE_FAILED",
                "Reasoning output could not be durably persisted.",
            )
        return {
            "reasoning_result": reasoning,
            "reasoning_persisted": True,
            "ai_reasoning_invoked": True,
            "llm_audit_complete": True,
            "llm_invocation_ids": [*state["llm_invocation_ids"], invocation_id],
            "reasoning_provider": response.provider,
            "reasoning_model": response.model,
            "prompt_hash": prompt_hash,
            "prompt_evidence_count": len(evidence_ids),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "estimated_cost": response.estimated_cost,
        }
