from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from urllib import request

from legacydb_copilot.agents.intent_agent import IntentResult
from legacydb_copilot.agents.reasoning_agent import ReasoningResult
from legacydb_copilot.config import Settings
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
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
- If evidence is insufficient, say confidence is low and list the missing evidence.
- You may improve wording, summarization, senior-engineer explanation, confidence explanation, and next investigative questions.
- Return only valid JSON matching the requested schema.
"""


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
    if not llm_reasoning_enabled(settings):
        return deterministic_reasoning

    payload = _build_llm_payload(
        question=question,
        intent=intent,
        deterministic_reasoning=deterministic_reasoning,
        evidence=evidence,
        correlated_evidence=correlated_evidence,
        procedure_analysis=procedure_analysis,
        documents=documents,
        evidence_focus=evidence_focus,
    )
    try:
        llm_json = _call_openai_responses(settings, payload)
        return _merge_llm_reasoning(deterministic_reasoning, llm_json)
    except Exception:
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
    return {
        "task": "Improve the database investigation reasoning using only this evidence. Do not create new SQL or facts.",
        "question": question,
        "detected_intent": intent.intent.value,
        "intent_confidence": intent.confidence,
        "deterministic_reasoning": {
            "summary": deterministic_reasoning.summary,
            "likely_root_causes": deterministic_reasoning.likely_root_causes,
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


def _call_openai_responses(settings: Settings, evidence_payload: dict[str, Any]) -> dict[str, Any]:
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
    with request.urlopen(http_request, timeout=30) as response:
        response_json = json.loads(response.read().decode("utf-8"))
    output_text = _extract_response_text(response_json)
    return json.loads(output_text)


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


def _merge_llm_reasoning(base: ReasoningResult, llm_json: dict[str, Any]) -> ReasoningResult:
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
    root_causes = _cited_items(llm_json.get("likely_root_causes"), "conclusion")
    fixes = _cited_items(llm_json.get("recommended_fix"), "step")
    proof = _cited_items(llm_json.get("proof_of_fix"), "step")
    risks = _cited_items(llm_json.get("risks"), "risk")
    next_questions = _cited_items(llm_json.get("recommended_next_questions"), "question")
    test_cases = _cited_test_cases(llm_json.get("test_cases"))
    if not root_causes:
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


def _cited_items(value: Any, text_key: str) -> list[str]:
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
    return items


def _cited_test_cases(value: Any) -> list[dict[str, str]]:
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
            continue
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
