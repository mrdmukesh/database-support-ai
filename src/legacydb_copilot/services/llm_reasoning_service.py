from __future__ import annotations

import json
import re
import random
import threading
import time
from dataclasses import replace
from typing import Any
from urllib import error, request

from legacydb_copilot.agents.intent_agent import IntentResult
from legacydb_copilot.agents.reasoning_agent import (
    RootCauseClaim,
    RootCauseSupportStatus,
    ReasoningResult,
    evaluate_claim_support_status,
)
from legacydb_copilot.config import Settings
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.pii_masking_service import mask_llm_payload, sanitize_ai_trace
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


SYSTEM_PROMPT = """You are an evidence-grounded database investigation reasoning layer.

Rules:
- Do not generate SQL.
- Do not ask to run SQL directly.
- Do not invent tables, procedures, business rules, rows, or errors.
- Reason only over the evidence payload provided by the deterministic application.
- Never override SQL evidence, metadata evidence, stored procedure analysis, or evidence-gate results.
- If the deterministic evidence contradicts a likely explanation, reject that explanation.
- Every root-cause conclusion, recommendation, test case, and proof-of-fix step must cite evidence_refs.
- Separate read-only investigation steps from controlled change proposals.
- Never present a write, destructive, irreversible, or recovery action as a direct instruction.
- A controlled change proposal must say not to execute it directly from the investigation and must require non-production validation, backup and rollback planning, explicit approval, and execution by an authorized operator.
- If evidence is insufficient, say confidence is low and list the missing evidence.
- You may improve wording, summarization, senior-engineer explanation, confidence explanation, and next investigative questions.
- Return only valid JSON matching the requested schema.
"""
AI_REASONING_PROMPT_VERSION = "evidence-grounded-v1"

_CONTROLLED_CHANGE = re.compile(
    r"\b(?:apply|implement|modify|change|fix|resolve|repair|"
    r"insert|update|delete|drop|alter|truncate|merge|create|execute|exec|grant|revoke)\b",
    re.I,
)


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
        debug_trace.setdefault("model", settings.llm_model)
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
    )
    payload = mask_llm_payload(raw_payload)
    if debug_trace is not None:
        debug_trace.update(
            {
                "llm_model_name": settings.llm_model,
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
        llm_json = _call_openai_responses(settings, payload, debug_trace=debug_trace)
        enhanced = _merge_llm_reasoning(deterministic_reasoning, llm_json, evidence_records=evidence, debug_trace=debug_trace)
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
            debug_trace["model_requested"] = settings.llm_model
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
) -> dict[str, Any]:
    evidence_items = [
        {
            "ref": f"SQL-{index}",
            "purpose": item.purpose,
            "sql_generated_by_safe_engine": item.sql,
            "row_count": len(item.rows),
            "sample_rows": item.rows[:5],
            "error": item.error,
        }
        for index, item in enumerate(evidence, start=1)
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
            "ref": f"EV-{index}",
            "type": item.evidence_type,
            "subject": item.subject,
            "finding": item.finding,
            "support": item.support,
            "confidence": item.confidence,
        }
        for index, item in enumerate(correlated_evidence[:20], start=1)
    ]
    payload = {
        "task": "Improve the database investigation reasoning using only this evidence. Do not create new SQL or facts.",
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
            "sql": evidence_items,
            "procedures": procedure_items,
            "documents": document_items,
            "correlated": correlated_items,
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
            "summary": "string",
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
    body = {
        "model": settings.llm_model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(evidence_payload, default=str)},
        ],
        "temperature": 0.1,
        "max_output_tokens": 2500,
    }
    data = json.dumps(body).encode("utf-8")
    http_request = request.Request(
        f"{settings.openai_base_url}/responses",
        data=data,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
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
        request_timeout = min(settings.llm_request_timeout_seconds, remaining)
        if debug_trace is not None:
            debug_trace["provider_attempt_count"] = attempt
        attempt_started = time.monotonic()
        try:
            with request.urlopen(http_request, timeout=request_timeout) as response:
                response_json = json.loads(response.read().decode("utf-8"))
            _PROVIDER_CIRCUIT.success()
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
    cited_root_causes = _cited_items(llm_json.get("likely_root_causes"), "conclusion", validation=validation)
    raw_root_causes = llm_json.get("likely_root_causes")
    generated_claim_count = len(
        [
            item
            for item in (raw_root_causes if isinstance(raw_root_causes, list) else [])
            if isinstance(item, dict) and str(item.get("conclusion") or "").strip()
        ]
    )
    root_causes = [
        claim
        for raw_claim in (raw_root_causes if isinstance(raw_root_causes, list) else [])
        if isinstance(raw_claim, dict) and raw_claim.get("evidence_refs")
        for claim in [convert_llm_claim_to_root_cause_claim(raw_claim, evidence_records or [])]
        if claim is not None
    ]
    verified_claim_count = len([claim for claim in root_causes if claim.status == RootCauseSupportStatus.VERIFIED])
    rejected_claim_count = max(generated_claim_count - verified_claim_count, 0)
    fixes = _safeguard_remediation_steps(
        _cited_items(llm_json.get("recommended_fix"), "step", validation=validation)
    )
    proof = _safeguard_remediation_steps(
        _cited_items(llm_json.get("proof_of_fix"), "step", validation=validation)
    )
    risks = _cited_items(llm_json.get("risks"), "risk", validation=validation)
    next_questions = _cited_items(llm_json.get("recommended_next_questions"), "question", validation=validation)
    test_cases = _cited_test_cases(llm_json.get("test_cases"), validation=validation)
    if debug_trace is not None:
        debug_trace["validated_citations"] = validation["accepted"]
        debug_trace["rejected_or_unsupported_claims"] = validation["rejected"]
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
            debug_trace["invocation_status"] = "completed_with_partial_verification"
            debug_trace["skip_reason"] = "none"
            debug_trace["verification_status"] = "partial"
        else:
            debug_trace["invocation_status"] = "completed"
            debug_trace["skip_reason"] = "none"
            debug_trace["verification_status"] = "verified"
    if not cited_root_causes or not root_causes:
        return base
    summary_parts = [str(llm_json.get("summary") or base.summary)]
    senior_explanation = str(llm_json.get("senior_engineer_explanation") or "").strip()
    clearer_wording = str(llm_json.get("clearer_report_wording") or "").strip()
    if senior_explanation:
        summary_parts.append(f"Senior engineer explanation: {senior_explanation}")
    if clearer_wording:
        summary_parts.append(f"Clearer report wording: {clearer_wording}")
    confidence_note = str(llm_json.get("confidence_note") or "").strip()
    if confidence_note:
        summary_parts.append(f"Confidence note: {confidence_note}")
    if next_questions:
        summary_parts.append("Recommended next questions: " + " ".join(next_questions))
    return replace(
        base,
        summary=" ".join(summary_parts),
        likely_root_causes=root_causes,
        missing_evidence=_string_list(llm_json.get("missing_evidence")) or base.missing_evidence,
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
        if text and refs:
            items.append(f"{text} Evidence: {', '.join(refs)}.")
            if validation is not None:
                validation["accepted"].append({"claim": text, "evidence_refs": refs})
        elif text and validation is not None:
            validation["rejected"].append({"claim": text, "reason": "Missing evidence_refs"})
    return items


def _cited_test_cases(
    value: Any,
    *,
    validation: dict[str, list[Any]] | None = None,
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
        if not refs:
            if validation is not None:
                validation["rejected"].append(
                    {"claim": str(item.get("scenario") or item.get("test_id") or "test case"), "reason": "Missing evidence_refs"}
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
