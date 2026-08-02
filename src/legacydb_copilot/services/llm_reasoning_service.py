from __future__ import annotations

import json
import random
import re
import threading
import time
from dataclasses import replace
from typing import Any
from urllib import error
from uuid import uuid4

from sqlalchemy.orm import Session

from legacydb_copilot.agents.intent_agent import IntentResult
from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    RootCauseClaim,
    RootCauseSupportStatus,
    evaluate_claim_support_status,
)
from legacydb_copilot.config import Settings
from legacydb_copilot.services.claim_verification_service import (
    build_evidence_registry,
    parse_structured_claim,
    verify_claim,
)
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.llm_invocation_audit_service import InvocationContext
from legacydb_copilot.services.llm_model_configuration import build_reasoning_parameters
from legacydb_copilot.services.llm_provider_client import (
    AuditedLLMProviderClient,
    ProviderRequest,
)
from legacydb_copilot.services.llm_provider_client import (
    request as request,  # noqa: F401 - compatibility for provider retry tests
)
from legacydb_copilot.services.pii_masking_service import mask_llm_payload, sanitize_ai_trace
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.reasoning_dispatch_service import ReasoningMode
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis

SYSTEM_PROMPT = """You are the evidence-grounded database investigation reasoning layer.

Architecture:
The application has already completed intent analysis, entity extraction, metadata discovery,
relationship discovery, safe SQL planning, SQL validation, SQL execution, evidence verification,
stored procedure analysis, metadata analysis, and Evidence Gate evaluation.
Your responsibility begins only after deterministic evidence collection.

Responsibilities:
- Explain verified findings.
- Correlate verified evidence.
- Produce an executive root-cause analysis.
- Summarize evidence gaps.
- Assess confidence.
- Suggest additional investigation questions.
- Recommend validation tests.
- Generate evidence-supported root-cause conclusions only when justified.

Restrictions:
- Do not generate new SQL.
- Do not request additional SQL execution.
- Do not invent database objects, procedures, jobs, tables, rows, errors, workflows, or business rules.
- Do not infer facts that are not supported by verified evidence.
- Never override deterministic SQL evidence, metadata evidence, stored procedure analysis,
  workflow analysis, or Evidence Gate decisions.
- Treat a successful zero-row result as verified absence only when its evidence_semantics is
  explicitly verified_absence. Otherwise describe it as an evidence gap, not proof of absence.
- Distinguish clearly between verified findings, verified absence, evidence gaps, inference, and hypothesis.
- If deterministic evidence contradicts a possible explanation, reject that explanation.
- Never fabricate a root cause.
- If multiple explanations remain possible, explain why they cannot yet be distinguished.
- If evidence is insufficient, explicitly state that the root cause is not established.
- Never contradict the deterministic investigation pipeline.

Recommendations:
- Separate investigation observations from change recommendations.
- Never present a database modification as an instruction.
- Every proposed change must be clearly marked as a controlled change proposal.
- Every controlled change proposal must state that it must be validated in non-production first,
  have a backup and rollback plan, receive required approvals, and be executed only by an
  authorized operator.

Evidence traceability:
- Every finding, root cause, recommendation, validation test, and proof-of-fix step must reference
  one or more evidence_refs.
- Use only exact citation IDs listed in citation_contract.valid_evidence_ids. Correlated context has
  no independent citation ID and must never be cited with an invented alias.

Output:
- Return only valid JSON matching the requested schema.
"""
AI_REASONING_PROMPT_VERSION = "evidence-grounded-v2-post-deterministic"

_CONTROLLED_CHANGE = re.compile(
    r"\b(?:apply|implement|modify|change|fix|resolve|repair|"
    r"insert|update|delete|drop|alter|truncate|merge|create|execute|exec|grant|revoke)\b",
    re.I,
)

_DOMAIN_TERMS = {
    "transfer": {"transfer", "source account", "destination account"},
    "payroll": {"payroll", "employee", "salary"},
    "shipping": {"shipment", "shipping", "carrier"},
    "order": {"order", "purchase"},
    "clinic": {"clinic", "encounter", "patient"},
}


def _domain_compatible(text: str, evidence_records: list[EvidenceResult]) -> bool:
    """Reject foreign-domain prose unless current evidence objects support that domain."""
    normalized = text.casefold()
    evidence_scope = " ".join(
        f"{item.purpose} {item.sql}"
        for item in evidence_records
    ).casefold()
    for terms in _DOMAIN_TERMS.values():
        if any(term in normalized for term in terms) and not any(
            term in evidence_scope for term in terms
        ):
            return False
    return True


def _safeguard_remediation_steps(steps: list[str]) -> list[str]:
    """Render model recommendations as read-only investigation or governed change proposals."""
    safeguarded: list[str] = []
    for raw_step in steps:
        step = str(raw_step).strip()
        if not step:
            continue
        if _CONTROLLED_CHANGE.search(step):
            safeguarded.append(
                "Controlled change proposal - do not execute directly from this investigation: "
                f"{step} Before execution, the proposed change must be validated in a "
                "non-production environment, have a verified backup and rollback plan, receive "
                "explicit change approval, and be performed by an authorized operator through "
                "the controlled change process."
            )
        else:
            safeguarded.append(f"Investigation step (read-only): {step}")
    return safeguarded


def convert_llm_claim_to_root_cause_claim(
    raw_claim: Any,
    evidence_records: list[EvidenceResult],
) -> RootCauseClaim | None:
    if not isinstance(raw_claim, dict):
        return None
    conclusion = str(raw_claim.get("conclusion") or "").strip()
    if not conclusion:
        return None
    raw_refs = raw_claim.get("evidence_refs")
    if isinstance(raw_refs, str):
        candidates = [raw_refs]
    elif isinstance(raw_refs, (list, tuple)):
        candidates = raw_refs
    else:
        candidates = []
    evidence_refs = [ref.strip() for ref in candidates if isinstance(ref, str) and ref.strip()]
    claim = RootCauseClaim(conclusion=conclusion, evidence_refs=evidence_refs)
    return evaluate_claim_support_status(claim, evidence_records)


def _root_cause_evidence_issue(
    claim: RootCauseClaim | None,
    evidence_records: list[EvidenceResult],
) -> str:
    """Reject causal claims that rely on failed or semantically unverified evidence."""
    if claim is None or claim.status is not RootCauseSupportStatus.VERIFIED:
        return ""
    evidence_by_id = {item.evidence_id: item for item in evidence_records}
    cited = [evidence_by_id[ref] for ref in claim.evidence_refs if ref in evidence_by_id]
    if any(item.execution_status != "succeeded" for item in cited):
        return "unsuccessful_evidence"
    if any(
        item.zero_row_result and item.evidence_semantics != "verified_absence"
        for item in cited
    ):
        return "unverified_negative_evidence"
    return ""


def llm_reasoning_enabled(settings: Settings | None = None) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles llm reasoning enabled within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Evidence package -> optional OpenAI reasoning -> citation-aware merge -> report.
    
    Safety considerations:
        The LLM must reason only over collected evidence and must never connect to databases or run SQL.
    """
    settings = settings or Settings.from_env()
    return bool(
        settings.ai_reasoning_enabled
        and settings.llm_provider == "openai"
        and settings.openai_api_key
    )


def enhance_reasoning_with_llm(
    *,
    question: str,
    intent: IntentResult,
    deterministic_reasoning: ReasoningResult,
    evidence: list[EvidenceResult],
    correlated_evidence: list[CorrelatedEvidence],
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None = None,
    settings: Settings | None = None,
    debug_trace: dict[str, Any] | None = None,
    audit_db: Session | None = None,
    audit_context: InvocationContext | None = None,
    reasoning_mode: ReasoningMode = ReasoningMode.NORMAL_ROOT_CAUSE,
) -> ReasoningResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Optionally improves explanation quality by asking OpenAI to reason over an already-collected evidence package.

    Input:
        User question, deterministic reasoning, SQL evidence, correlated findings, procedure analysis, documents,
        and evidence focus.

    Output:
        ReasoningResult enhanced with evidence-cited narrative, or the original deterministic result on failure.

    Called by:
        Main /chat/ask orchestration after SQL evidence collection and deterministic reasoning.

    Flow:
        Safe evidence package -> OpenAI reasoning request -> citation validation/merge -> report composer.

    Safety:
        The LLM never receives database credentials, never connects to the database, never executes SQL, and cannot
        override collected SQL evidence. Failures fall back to deterministic reasoning.
    """

    settings = settings or Settings.from_env()
    if debug_trace is not None:
        debug_trace.setdefault("ai_enabled", bool(settings.ai_reasoning_enabled))
        debug_trace.setdefault("provider", settings.llm_provider)
        debug_trace.setdefault("model", settings.selected_reasoning_model)
        debug_trace.setdefault("llm_invoked", False)
        debug_trace.setdefault("invocation_status", "not_invoked")
        debug_trace.setdefault("generated_claim_count", 0)
        debug_trace.setdefault("verified_claim_count", 0)
        debug_trace.setdefault("rejected_claim_count", 0)
        debug_trace.setdefault("verification_status", "not_applicable")
        debug_trace.setdefault("skip_reason", "llm_not_configured")
        debug_trace.setdefault("error_category", None)
    if not llm_reasoning_enabled(settings):
        if debug_trace is not None:
            if not settings.ai_reasoning_enabled:
                debug_trace["skip_reason"] = "ai_reasoning_disabled"
            elif settings.llm_provider != "openai":
                debug_trace["skip_reason"] = "provider_not_supported"
            elif not settings.openai_api_key:
                debug_trace["skip_reason"] = "missing_openai_api_key"
            else:
                debug_trace["skip_reason"] = "llm_not_configured"
            debug_trace["invocation_status"] = "skipped"
        return deterministic_reasoning

    raw_payload = _build_llm_payload_unmasked(
        question=question,
        intent=intent,
        deterministic_reasoning=deterministic_reasoning,
        evidence=evidence,
        correlated_evidence=correlated_evidence,
        procedure_analysis=procedure_analysis,
        documents=documents,
        evidence_focus=evidence_focus,
        reasoning_mode=reasoning_mode,
    )
    payload = mask_llm_payload(raw_payload)
    if debug_trace is not None:
        debug_trace.update(
            {
                "llm_model_name": settings.selected_reasoning_model,
                "prompt_version": AI_REASONING_PROMPT_VERSION,
                "ai_reasoning_invoked": False,
                "input_tokens": 0,
                "output_tokens": 0,
                "validated_citations": [],
                "rejected_or_unsupported_claims": [],
                "final_report_claims": deterministic_reasoning.likely_root_causes,
                "llm_invoked": False,
                "invocation_status": "pending",
                "skip_reason": "awaiting_provider_response",
            }
        )
        if settings.ai_debug_trace_enabled:
            debug_trace.update(
                {
                    "system_prompt": SYSTEM_PROMPT,
                    "user_prompt": json.dumps(sanitize_ai_trace(payload), default=str),
                    "evidence_package_before_masking_summary": _payload_summary(raw_payload),
                    "evidence_package_after_masking": sanitize_ai_trace(payload),
                    "llm_response_raw": None,
                }
            )
    try:
        audit_kwargs = (
            {"audit_db": audit_db, "audit_context": audit_context}
            if audit_db is not None and audit_context is not None
            else {}
        )
        llm_json = _call_openai_responses(
            settings, payload, debug_trace=debug_trace, **audit_kwargs,
        )
        enhanced = _merge_llm_reasoning(
            deterministic_reasoning,
            llm_json,
            evidence_records=evidence,
            correlated_evidence=correlated_evidence,
            procedure_analysis=procedure_analysis,
            debug_trace=debug_trace,
        )
        if reasoning_mode in {
            ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
            ReasoningMode.EVIDENCE_GAP_SUMMARY,
            ReasoningMode.PARTIAL_EVIDENCE_SUMMARY,
        }:
            enhanced = replace(
                deterministic_reasoning,
                likely_root_causes=deterministic_reasoning.likely_root_causes,
                recommended_fix=deterministic_reasoning.recommended_fix,
                proof_of_fix=deterministic_reasoning.proof_of_fix,
                response_type=reasoning_mode.value.casefold(),
            )
        if debug_trace is not None:
            if settings.ai_debug_trace_enabled:
                debug_trace["llm_response_raw"] = sanitize_ai_trace(mask_llm_payload(llm_json))
            debug_trace["final_report_claims"] = enhanced.likely_root_causes
        return enhanced
    except Exception as exc:
        if debug_trace is not None:
            debug_trace["ai_reasoning_error"] = type(exc).__name__
            debug_trace["ai_outcome"] = "provider_failure"
            debug_trace["failure_stage"] = "provider_request_or_response"
            debug_trace["request_submitted"] = bool(debug_trace.get("ai_reasoning_invoked"))
            debug_trace["provider"] = settings.llm_provider
            debug_trace["model_requested"] = settings.selected_reasoning_model
            debug_trace["sanitized_error_reason"] = type(exc).__name__
            debug_trace["llm_invoked"] = bool(debug_trace.get("ai_reasoning_invoked"))
            debug_trace["invocation_status"] = "provider_failure"
            debug_trace["skip_reason"] = "provider_error"
            debug_trace["verification_status"] = "failed"
            debug_trace["error_category"] = type(exc).__name__
        return deterministic_reasoning


def _build_llm_payload(
    *,
    question: str,
    intent: IntentResult,
    deterministic_reasoning: ReasoningResult,
    evidence: list[EvidenceResult],
    correlated_evidence: list[CorrelatedEvidence],
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None,
    reasoning_mode: ReasoningMode = ReasoningMode.NORMAL_ROOT_CAUSE,
) -> dict[str, Any]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for build llm payload within llm_reasoning_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in llm_reasoning_service.py.
    
    Where it fits in the flow:
        Evidence package -> optional OpenAI reasoning -> citation-aware merge -> report.
    
    Safety considerations:
        The LLM must reason only over collected evidence and must never connect to databases or run SQL.
    """
    return mask_llm_payload(
        _build_llm_payload_unmasked(
            question=question,
            intent=intent,
            deterministic_reasoning=deterministic_reasoning,
            evidence=evidence,
            correlated_evidence=correlated_evidence,
            procedure_analysis=procedure_analysis,
            documents=documents,
            evidence_focus=evidence_focus,
            reasoning_mode=reasoning_mode,
        )
    )


def _build_llm_payload_unmasked(
    *,
    question: str,
    intent: IntentResult,
    deterministic_reasoning: ReasoningResult,
    evidence: list[EvidenceResult],
    correlated_evidence: list[CorrelatedEvidence],
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None,
    reasoning_mode: ReasoningMode = ReasoningMode.NORMAL_ROOT_CAUSE,
) -> dict[str, Any]:
    canonical_evidence = build_evidence_registry(
        evidence, procedure_analysis, correlated_evidence
    )
    evidence_items = [
        {
            "ref": item.evidence_id,
            "evidence_id": item.evidence_id,
            "type": item.type,
            "title": item.title,
            "purpose": item.title,
            "sql": item.sql,
            "sql_generated_by_safe_engine": item.sql,
            "columns": list(item.columns),
            "rows": list(item.rows),
            "sample_rows": list(item.rows),
            "row_count": item.row_count,
            "zero_row_result": item.zero_row_result,
            "evidence_semantics": item.evidence_semantics,
            "supports_claim": item.supports_claim,
            "included_in_prompt": item.included_in_prompt,
            "truncated": item.truncated,
        }
        for item in canonical_evidence
        if item.type in {"SQL_RESULT", "COLLECTED_EVIDENCE"}
    ]
    procedure_items = [
        {
            "ref": f"PROC-{index}",
            "name": item.name,
            "definition_available": item.definition_available,
            "tables_read": item.tables_read,
            "tables_written": item.tables_written,
            "complexity": item.complexity,
            "locking_risk": item.locking_risk,
            "business_rules": item.business_rules,
            "definition_excerpt": item.definition_excerpt[:1500],
        }
        for index, item in enumerate(procedure_analysis, start=1)
    ]
    document_items = [
        {
            "ref": f"DOC-{index}",
            "title": item.title,
            "snippet": item.snippet[:1500],
        }
        for index, item in enumerate(documents[:8], start=1)
    ]
    correlated_items = [
        {
            "type": item.evidence_type,
            "subject": item.subject,
            "finding": item.finding,
            "support": item.support,
            "confidence": item.confidence,
        }
        for index, item in enumerate(correlated_evidence[:20], start=1)
    ]
    summary_only = reasoning_mode in {
        ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
        ReasoningMode.EVIDENCE_GAP_SUMMARY,
        ReasoningMode.PARTIAL_EVIDENCE_SUMMARY,
    }
    summary_task = (
        "Summarize only verified findings, reproduction status, observed system or workflow state, evidence gaps, "
        "and confidence. State that root cause was not established from the available evidence. Do not infer a "
        "root cause, recommend corrective action, or create new SQL or facts."
        if reasoning_mode != ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED
        else
        "Summarize only verified findings, reproduction result, observed system state, evidence gaps, and "
        "confidence. State clearly that verified evidence was collected but the reported condition could not be "
        "reproduced, and that root cause was not established. Do not infer or recommend a root cause or corrective "
        "action, and do not create new SQL or facts."
    )
    payload = {
        "reasoning_mode": reasoning_mode.value,
        "task": (
            summary_task
            if summary_only
            else "Improve the database investigation reasoning using only this evidence. Do not create new SQL or facts."
        ),
        "question": question,
        "detected_intent": intent.intent.value,
        "intent_confidence": intent.confidence,
        "deterministic_reasoning": {
            "summary": deterministic_reasoning.summary,
            "likely_root_causes": [claim.conclusion for claim in deterministic_reasoning.likely_root_causes],
            "supporting_evidence": deterministic_reasoning.supporting_evidence,
            "missing_evidence": deterministic_reasoning.missing_evidence,
            "recommended_fix": deterministic_reasoning.recommended_fix,
            "test_cases": deterministic_reasoning.test_cases,
            "proof_of_fix": deterministic_reasoning.proof_of_fix,
            "rollback_plan": deterministic_reasoning.rollback_plan,
            "risks": deterministic_reasoning.risks,
        },
        "evidence_refs": {
            "canonical": [item.to_prompt_dict() for item in canonical_evidence],
            "sql": evidence_items,
            "procedures": procedure_items,
            "documents": document_items,
            "correlated": correlated_items,
        },
        "citation_contract": {
            "valid_evidence_ids": list(
                dict.fromkeys(
                    [
                        *[str(item["ref"]) for item in evidence_items],
                        *[str(item["ref"]) for item in procedure_items],
                    ]
                )
            ),
            "instruction": (
                "Use only the exact IDs in valid_evidence_ids for evidence_refs. "
                "Correlated entries are explanatory context derived from persisted evidence "
                "and are not independently citable. Never invent, alias, or renumber an ID."
            ),
        },
        "evidence_focus": {
            "affected_object": evidence_focus.affected_object,
            "affected_object_reason": evidence_focus.affected_object_reason,
            "inferred_business_key": evidence_focus.inferred_business_key,
            "business_key_reason": evidence_focus.business_key_reason,
            "confirmed_facts": evidence_focus.confirmed_facts,
            "inferred_findings": evidence_focus.inferred_findings,
            "hypotheses": evidence_focus.hypotheses,
        }
        if evidence_focus
        else None,
        "required_json_schema": {
            "claims": [{
                "claim_id": "CL-001",
                "statement": "string",
                "claim_type": "VERIFIED_FINDING | EVIDENCE_GAP",
                "evidence_ids": ["SQL-1"],
                "evidence_gap": None,
                "recommended_action": None,
            }],
            "summary": "string",
            "verified_findings": [{"finding": "string", "evidence_refs": ["SQL-1", "PROC-1"]}],
            "verified_absences": [{"finding": "string", "evidence_refs": ["SQL-1"]}],
            "evidence_gaps": [{"gap": "string", "evidence_refs": ["SQL-1", "PROC-1"]}],
            "senior_engineer_explanation": "string",
            "confidence_note": "string",
            "likely_root_causes": [{"conclusion": "string", "evidence_refs": ["SQL-1", "PROC-1"]}],
            "missing_evidence": ["string"],
            "recommended_fix": [{"step": "string", "evidence_refs": ["SQL-1"]}],
            "recommended_next_questions": [{"question": "string", "evidence_refs": ["SQL-1"]}],
            "clearer_report_wording": "string",
            "test_cases": [{"test_id": "string", "scenario": "string", "steps": "string", "expected_result": "string", "evidence_refs": ["SQL-1"]}],
            "proof_of_fix": [{"step": "string", "evidence_refs": ["SQL-1"]}],
            "risks": [{"risk": "string", "evidence_refs": ["SQL-1"]}],
        },
    }
    return payload


def _call_openai_responses(
    settings: Settings,
    evidence_payload: dict[str, Any],
    *,
    debug_trace: dict[str, Any] | None = None,
    audit_db: Session | None = None,
    audit_context: InvocationContext | None = None,
) -> dict[str, Any]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for call openai responses within llm_reasoning_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in llm_reasoning_service.py.
    
    Where it fits in the flow:
        Evidence package -> optional OpenAI reasoning -> citation-aware merge -> report.
    
    Safety considerations:
        The LLM must reason only over collected evidence and must never connect to databases or run SQL.
    """
    request_parameters, unsupported_parameters = build_reasoning_parameters(
        model=settings.selected_reasoning_model,
        reasoning_effort=settings.llm_reasoning_effort,
        max_output_tokens=settings.llm_max_output_tokens,
    )
    body = {
        "model": settings.selected_reasoning_model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(evidence_payload, default=str)},
        ],
        **request_parameters,
    }
    if "reasoning" not in request_parameters:
        body["temperature"] = 0.1
    if debug_trace is not None:
        debug_trace["reasoning_effort"] = (
            settings.llm_reasoning_effort if "reasoning" in request_parameters else None
        )
        debug_trace["unsupported_model_parameters"] = list(unsupported_parameters)
    if audit_context is not None and audit_context.logical_request_id is None:
        audit_context = replace(audit_context, logical_request_id=str(uuid4()))
    provider_client = AuditedLLMProviderClient(db=audit_db, context=audit_context)
    attempts = max(1, settings.llm_retry_attempts)
    deadline = time.monotonic() + settings.llm_total_timeout_seconds
    response_json: dict[str, Any] | None = None
    if debug_trace is not None:
        debug_trace["ai_reasoning_invoked"] = True
        debug_trace["provider_attempt_count"] = 0
        debug_trace["provider_retry_count"] = 0
        debug_trace["provider_attempts"] = []
    for attempt in range(1, attempts + 1):
        now = time.monotonic()
        _PROVIDER_CIRCUIT.before_call(
            threshold=settings.llm_circuit_breaker_threshold,
            cooldown=settings.llm_circuit_breaker_cooldown_seconds,
            now=now,
        )
        remaining = deadline - now
        if remaining <= 0:
            raise TimeoutError("LLM provider total timeout exhausted")
        request_timeout = min(settings.selected_provider_timeout_seconds, remaining)
        if debug_trace is not None:
            debug_trace["provider_attempt_count"] = attempt
        attempt_started = time.monotonic()
        try:
            response_json = provider_client.invoke_json(ProviderRequest(
                provider=settings.llm_provider,
                model=settings.selected_reasoning_model,
                endpoint=f"{settings.openai_base_url}/responses",
                api_key=settings.openai_api_key or "",
                body=body,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=json.dumps(evidence_payload, default=str),
                timeout_seconds=request_timeout,
                retry_attempt=attempt,
                will_retry_on_failure=attempt < attempts,
                prompt_template_name="root_cause_reasoning",
                prompt_template_version=AI_REASONING_PROMPT_VERSION,
                input_cost_per_million=settings.llm_input_cost_per_million,
                output_cost_per_million=settings.llm_output_cost_per_million,
            ))
            _PROVIDER_CIRCUIT.success()
            incomplete_reason = (
                response_json.get("incomplete_details", {}).get("reason")
                if isinstance(response_json.get("incomplete_details"), dict)
                else None
            )
            if (
                response_json.get("status") == "incomplete"
                and incomplete_reason == "max_output_tokens"
                and attempt < attempts
                and isinstance(body.get("reasoning"), dict)
                and body["reasoning"].get("effort") != "low"
            ):
                if debug_trace is not None:
                    debug_trace["provider_attempts"].append({
                        "attempt": attempt,
                        "outcome": "incomplete",
                        "reason": incomplete_reason,
                        "duration_ms": int((time.monotonic() - attempt_started) * 1000),
                    })
                    debug_trace["provider_retry_count"] = attempt
                body["reasoning"] = {"effort": "low"}
                continue
            if debug_trace is not None:
                debug_trace["provider_attempts"].append({
                    "attempt": attempt, "outcome": "success",
                    "duration_ms": int((time.monotonic() - attempt_started) * 1000),
                })
            break
        except Exception as exc:
            retryable = _is_transient_provider_error(exc)
            status_code = exc.code if isinstance(exc, error.HTTPError) else None
            if retryable:
                _PROVIDER_CIRCUIT.transient_failure(
                    threshold=settings.llm_circuit_breaker_threshold,
                    now=time.monotonic(),
                )
            if debug_trace is not None:
                debug_trace["provider_attempts"].append(
                    {
                        "attempt": attempt, "outcome": "failed", "error": type(exc).__name__,
                        "http_status": status_code, "retryable": retryable,
                        "duration_ms": int((time.monotonic() - attempt_started) * 1000),
                    }
                )
                debug_trace["provider_error_type"] = type(exc).__name__
                debug_trace["provider_http_status"] = status_code
            if not retryable or attempt >= attempts:
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("LLM provider total timeout exhausted") from exc
            jitter = random.uniform(0.0, settings.llm_retry_jitter_seconds)
            backoff = min(settings.llm_retry_backoff_seconds * (2 ** (attempt - 1)) + jitter, remaining)
            if debug_trace is not None:
                debug_trace["provider_retry_count"] = attempt
            if backoff > 0:
                time.sleep(backoff)
    if response_json is None:
        raise TimeoutError("LLM provider returned no response")
    if debug_trace is not None:
        usage = response_json.get("usage") if isinstance(response_json.get("usage"), dict) else {}
        debug_trace["input_tokens"] = int(usage.get("input_tokens") or 0)
        debug_trace["output_tokens"] = int(usage.get("output_tokens") or 0)
        debug_trace["response_id_present"] = bool(response_json.get("id"))
    output_text = _extract_response_text(response_json)
    return json.loads(output_text)


def _is_transient_provider_error(exc: Exception) -> bool:
    """Return true only for connection-level failures that are safe to retry."""
    if isinstance(exc, error.HTTPError):
        return exc.code == 429 or 500 <= exc.code < 600
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, error.URLError):
        return isinstance(exc.reason, (TimeoutError, ConnectionError, OSError))
    return False


def _extract_response_text(response_json: dict[str, Any]) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for extract response text within llm_reasoning_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in llm_reasoning_service.py.
    
    Where it fits in the flow:
        Evidence package -> optional OpenAI reasoning -> citation-aware merge -> report.
    
    Safety considerations:
        The LLM must reason only over collected evidence and must never connect to databases or run SQL.
    """
    if isinstance(response_json.get("output_text"), str):
        return response_json["output_text"]
    chunks: list[str] = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks)


def _merge_llm_reasoning(
    base: ReasoningResult,
    llm_json: dict[str, Any],
    *,
    evidence_records: list[EvidenceResult] | None = None,
    correlated_evidence: list[CorrelatedEvidence] | None = None,
    procedure_analysis: list[ProcedureAnalysis] | None = None,
    debug_trace: dict[str, Any] | None = None,
) -> ReasoningResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for merge llm reasoning within llm_reasoning_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in llm_reasoning_service.py.
    
    Where it fits in the flow:
        Evidence package -> optional OpenAI reasoning -> citation-aware merge -> report.
    
    Safety considerations:
        The LLM must reason only over collected evidence and must never connect to databases or run SQL.
    """
    validation: dict[str, list[Any]] = {"accepted": [], "rejected": []}
    raw_root_causes = (
        llm_json.get("claims")
        if isinstance(llm_json.get("claims"), list)
        else llm_json.get("likely_root_causes")
    )
    raw_root_causes = raw_root_causes if isinstance(raw_root_causes, list) else []
    registry = build_evidence_registry(
        evidence_records or [],
        procedure_analysis or [],
        correlated_evidence or [],
    )
    claim_diagnostics: list[dict[str, Any]] = []
    root_causes: list[RootCauseClaim] = []
    evidence_gap_claims: list[str] = []
    supported_observations: list[str] = []
    evidence_by_id = {
        item.evidence_id: item for item in (evidence_records or [])
    }
    for index, raw_claim in enumerate(raw_root_causes, start=1):
        parsed = parse_structured_claim(raw_claim, index)
        if parsed is None:
            continue
        decision = verify_claim(parsed, registry)
        diagnostic = decision.to_dict()
        if not _domain_compatible(parsed.statement, evidence_records or []):
            supported_observations.extend(
                observation
                for ref in decision.evidence_ids_resolved
                for observation in [
                    str(evidence_by_id.get(ref).supports_claim or "").strip()
                    if evidence_by_id.get(ref)
                    else ""
                ]
                if observation
            )
            diagnostic.update(
                verification_result="REJECTED",
                rejection_code="domain_mismatch",
                rejection_detail=(
                    "Claim terminology does not match the investigation evidence domain."
                ),
            )
            claim_diagnostics.append(diagnostic)
            validation["rejected"].append(
                {
                    "claim": parsed.statement,
                    "claim_id": parsed.claim_id,
                    "decision": "excluded_from_report",
                    "reason": "domain_mismatch",
                    "detail": diagnostic["rejection_detail"],
                    "missing_evidence_refs": [],
                    "contradictory_evidence_ids": [],
                }
            )
            continue
        claim_diagnostics.append(diagnostic)
        if decision.verification_result == "VERIFIED":
            root_causes.append(
                RootCauseClaim(
                    conclusion=parsed.statement,
                    evidence_refs=list(decision.evidence_ids_resolved),
                    status=RootCauseSupportStatus.VERIFIED,
                )
            )
            validation["accepted"].append(
                {
                    "claim": parsed.statement,
                    "claim_id": parsed.claim_id,
                    "evidence_refs": list(decision.evidence_ids_resolved),
                }
            )
        elif decision.verification_result == "EVIDENCE_GAP":
            evidence_gap_claims.append(parsed.evidence_gap or parsed.statement)
        else:
            supported_observations.extend(
                observation
                for ref in decision.evidence_ids_resolved
                for observation in [
                    str(evidence_by_id.get(ref).supports_claim or "").strip()
                    if evidence_by_id.get(ref)
                    else ""
                ]
                if observation
            )
            validation["rejected"].append(
                {
                    "claim": parsed.statement,
                    "claim_id": parsed.claim_id,
                    "decision": "excluded_from_report",
                    "reason": (
                        "unverified_negative_evidence"
                        if decision.rejection_code
                        == "UNVERIFIED_NEGATIVE_EVIDENCE"
                        else decision.rejection_code
                    ),
                    "detail": decision.rejection_detail,
                    "missing_evidence_refs": [
                        ref
                        for ref in decision.evidence_ids_requested
                        if ref not in decision.evidence_ids_resolved
                    ],
                    "valid_evidence_refs": list(
                        decision.evidence_ids_resolved
                    ),
                    "contradictory_evidence_ids": list(
                        decision.contradictory_evidence_ids
                    ),
                }
            )
    generated_claim_count = len(claim_diagnostics)
    root_causes = [
        claim
        for claim in root_causes
        if _domain_compatible(claim.conclusion, evidence_records or [])
    ]
    verified_claim_count = len([claim for claim in root_causes if claim.status == RootCauseSupportStatus.VERIFIED])
    rejected_claim_count = sum(
        item["verification_result"] == "REJECTED" for item in claim_diagnostics
    )
    available_evidence_ids = {item.evidence_id for item in registry}
    fixes = _safeguard_remediation_steps(
        _cited_items(
            llm_json.get("recommended_fix"),
            "step",
            validation=validation,
            available_evidence_ids=available_evidence_ids,
        )
    )
    proof = _safeguard_remediation_steps(
        _cited_items(
            llm_json.get("proof_of_fix"),
            "step",
            validation=validation,
            available_evidence_ids=available_evidence_ids,
        )
    )
    risks = _cited_items(
        llm_json.get("risks"),
        "risk",
        validation=validation,
        available_evidence_ids=available_evidence_ids,
    )
    next_questions = _cited_items(
        llm_json.get("recommended_next_questions"),
        "question",
        validation=validation,
        available_evidence_ids=available_evidence_ids,
    )
    test_cases = _cited_test_cases(
        llm_json.get("test_cases"),
        validation=validation,
        available_evidence_ids=available_evidence_ids,
    )
    if debug_trace is not None:
        debug_trace["validated_citations"] = validation["accepted"]
        debug_trace["rejected_or_unsupported_claims"] = validation["rejected"]
        debug_trace["claim_verification_diagnostics"] = claim_diagnostics
        debug_trace["evidence_reference_registry"] = [
            {
                "evidence_id": item.evidence_id,
                "type": item.type,
                "title": item.title,
                "columns": list(item.columns),
                "row_count": item.row_count,
                "zero_row_result": item.zero_row_result,
                "included_in_prompt": item.included_in_prompt,
                "truncated": item.truncated,
            }
            for item in registry
        ]
        debug_trace["evidence_items_created"] = len(registry)
        debug_trace["evidence_items_sent_to_llm"] = sum(
            item.included_in_prompt and not item.truncated for item in registry
        )
        debug_trace["evidence_items_truncated"] = sum(
            item.truncated or not item.included_in_prompt for item in registry
        )
        debug_trace["claims_generated"] = generated_claim_count
        debug_trace["claims_parsed"] = len(claim_diagnostics)
        debug_trace["claims_verified"] = verified_claim_count
        debug_trace["claims_rejected"] = rejected_claim_count
        debug_trace["citation_resolution_failures"] = sum(
            item["rejection_code"]
            in {"EVIDENCE_ID_NOT_FOUND", "MISSING_CITATIONS", "EVIDENCE_NOT_IN_PROMPT"}
            for item in claim_diagnostics
        )
        debug_trace["llm_invoked"] = bool(debug_trace.get("ai_reasoning_invoked"))
        debug_trace["generated_claim_count"] = generated_claim_count
        debug_trace["verified_claim_count"] = verified_claim_count
        debug_trace["rejected_claim_count"] = rejected_claim_count
        debug_trace["error_category"] = None
        if generated_claim_count == 0:
            debug_trace["invocation_status"] = "completed_zero_claims"
            debug_trace["skip_reason"] = "llm_returned_zero_claims"
            debug_trace["verification_status"] = "no_claims"
        elif verified_claim_count == 0:
            debug_trace["invocation_status"] = "completed_no_verified_claims"
            debug_trace["skip_reason"] = "llm_claims_unverified_or_missing_citations"
            debug_trace["verification_status"] = "none_verified"
        elif rejected_claim_count > 0:
            debug_trace["invocation_status"] = "completed_partial_verification"
            debug_trace["skip_reason"] = "none"
            debug_trace["verification_status"] = "partial"
        else:
            debug_trace["invocation_status"] = "completed"
            debug_trace["skip_reason"] = "none"
            debug_trace["verification_status"] = "verified"
        debug_trace["final_reasoning_status"] = debug_trace["invocation_status"]
    narrowed_facts = list(
        dict.fromkeys([*base.confirmed_facts, *supported_observations])
    )
    if not root_causes:
        return (
            replace(base, confirmed_facts=narrowed_facts)
            if narrowed_facts != base.confirmed_facts
            else base
        )
    # Raw provider narrative is audit-only. Visible prose is composed from the
    # deterministic summary and claims that passed evidence-reference validation.
    summary_parts = [base.summary]
    summary_parts.extend(claim.conclusion for claim in root_causes)
    if next_questions:
        summary_parts.append("Recommended next questions: " + " ".join(next_questions))
    return replace(
        base,
        summary=" ".join(summary_parts),
        likely_root_causes=root_causes,
        confirmed_facts=narrowed_facts,
        missing_evidence=(
            evidence_gap_claims
            or _string_list(llm_json.get("missing_evidence"))
            or base.missing_evidence
        ),
        recommended_fix=fixes or base.recommended_fix,
        test_cases=test_cases or base.test_cases,
        proof_of_fix=proof or base.proof_of_fix,
        risks=risks or base.risks,
    )


def _cited_items(
    value: Any,
    text_key: str,
    *,
    validation: dict[str, list[Any]] | None = None,
    available_evidence_ids: set[str] | None = None,
) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for cited items within llm_reasoning_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in llm_reasoning_service.py.
    
    Where it fits in the flow:
        Evidence package -> optional OpenAI reasoning -> citation-aware merge -> report.
    
    Safety considerations:
        The LLM must reason only over collected evidence and must never connect to databases or run SQL.
    """
    items: list[str] = []
    if not isinstance(value, list):
        return items
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get(text_key) or "").strip()
        refs = [str(ref) for ref in item.get("evidence_refs") or [] if ref]
        invalid_refs = [ref for ref in refs if available_evidence_ids is not None and ref not in available_evidence_ids]
        if text and refs and not invalid_refs:
            items.append(f"{text} Evidence: {', '.join(refs)}.")
            if validation is not None:
                validation["accepted"].append({"claim": text, "evidence_refs": refs})
        elif text and validation is not None:
            validation["rejected"].append({
                "claim": text,
                "reason": "missing_evidence_refs" if not refs else "invalid_evidence_refs",
                "missing_evidence_refs": invalid_refs,
                "decision": "excluded_from_report",
            })
    return items


def _cited_test_cases(
    value: Any,
    *,
    validation: dict[str, list[Any]] | None = None,
    available_evidence_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for cited test cases within llm_reasoning_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in llm_reasoning_service.py.
    
    Where it fits in the flow:
        Evidence package -> optional OpenAI reasoning -> citation-aware merge -> report.
    
    Safety considerations:
        The LLM must reason only over collected evidence and must never connect to databases or run SQL.
    """
    cases: list[dict[str, str]] = []
    if not isinstance(value, list):
        return cases
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        refs = [str(ref) for ref in item.get("evidence_refs") or [] if ref]
        invalid_refs = [ref for ref in refs if available_evidence_ids is not None and ref not in available_evidence_ids]
        if not refs or invalid_refs:
            if validation is not None:
                validation["rejected"].append(
                    {
                        "claim": str(item.get("scenario") or item.get("test_id") or "test case"),
                        "reason": "missing_evidence_refs" if not refs else "invalid_evidence_refs",
                        "missing_evidence_refs": invalid_refs,
                        "decision": "excluded_from_report",
                    }
                )
            continue
        if validation is not None:
            validation["accepted"].append({"claim": str(item.get("scenario") or item.get("test_id") or "test case"), "evidence_refs": refs})
        cases.append(
            {
                "Test ID": str(item.get("test_id") or f"TC-{index:03d}"),
                "Scenario": str(item.get("scenario") or "Evidence-grounded validation"),
                "Steps": str(item.get("steps") or ""),
                "Expected Result": f"{item.get('expected_result') or ''} Evidence: {', '.join(refs)}.",
                "Actual Result": "Pending",
                "Status": "Pending",
            }
        )
    return cases


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    evidence_refs = payload.get("evidence_refs") if isinstance(payload, dict) else {}
    evidence_refs = evidence_refs if isinstance(evidence_refs, dict) else {}
    sql_summary = [
        {
            "evidence_id": item.get("ref"),
            "evidence_type": "SQL",
            "source_object": item.get("purpose"),
            "sql_result_summary": item.get("error") or f"{item.get('row_count', 0)} row(s) returned",
        }
        for item in (evidence_refs.get("sql") or [])
        if isinstance(item, dict)
    ]
    procedure_summary = [
        {
            "evidence_id": item.get("ref"),
            "evidence_type": "Procedure",
            "source_object": item.get("name"),
            "procedure_evidence": {
                "definition_available": item.get("definition_available"),
                "tables_read": item.get("tables_read") or [],
                "tables_written": item.get("tables_written") or [],
                "complexity": item.get("complexity"),
                "locking_risk": item.get("locking_risk"),
            },
        }
        for item in (evidence_refs.get("procedures") or [])
        if isinstance(item, dict)
    ]
    relationship_summary = [
        {
            "evidence_id": item.get("ref"),
            "evidence_type": item.get("type"),
            "source_object": item.get("subject"),
            "relationship_evidence": item.get("finding"),
            "support": item.get("support"),
        }
        for item in (evidence_refs.get("correlated") or [])
        if isinstance(item, dict)
    ]
    return {
        "question_present": bool(payload.get("question")),
        "detected_intent": payload.get("detected_intent"),
        "sql_evidence_count": len(evidence_refs.get("sql") or []),
        "procedure_evidence_count": len(evidence_refs.get("procedures") or []),
        "document_evidence_count": len(evidence_refs.get("documents") or []),
        "correlated_evidence_count": len(evidence_refs.get("correlated") or []),
        "sql_evidence": sql_summary[:20],
        "procedure_evidence": procedure_summary[:20],
        "relationship_evidence": relationship_summary[:20],
        "contains_raw_rows": False,
        "note": "Summary only; unmasked rows and PII are not persisted in AI debug trace.",
    }


def _string_list(value: Any) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for string list within llm_reasoning_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in llm_reasoning_service.py.
    
    Where it fits in the flow:
        Evidence package -> optional OpenAI reasoning -> citation-aware merge -> report.
    
    Safety considerations:
        The LLM must reason only over collected evidence and must never connect to databases or run SQL.
    """
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


class ProviderCircuitOpenError(RuntimeError):
    """Raised before submission while repeated transient failures cool down."""


class _ProviderCircuitBreaker:
    def __init__(self) -> None:
        self.failures = 0
        self.opened_at: float | None = None
        self._lock = threading.Lock()

    def before_call(self, *, threshold: int, cooldown: float, now: float) -> None:
        with self._lock:
            if self.opened_at is None:
                return
            if now - self.opened_at >= cooldown:
                self.failures = 0
                self.opened_at = None
                return
            raise ProviderCircuitOpenError("LLM provider circuit is open after repeated transient failures")

    def success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None

    def transient_failure(self, *, threshold: int, now: float) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= threshold:
                self.opened_at = now

    def reset(self) -> None:
        self.success()


_PROVIDER_CIRCUIT = _ProviderCircuitBreaker()
