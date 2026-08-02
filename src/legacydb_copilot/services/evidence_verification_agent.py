from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import ReasoningResult
from legacydb_copilot.services.diagnostic_object_service import contains_diagnostic_reference
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus, ProcedureRank
from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.safe_sql_service import validate_read_only_sql
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


@dataclass(frozen=True)
class SuggestedVerificationCheck:
    """
    Owner: Mukesh Dabi
    Purpose:
        Describes a human-approved read-only verification check suggested after an investigation.

    Input:
        A report claim, safe verification SQL, expected result, source, and optional explanatory text.

    Output:
        Structured check details shown in the UI and copied into generated reports.

    Called by:
        suggest_verification_checks() after evidence collection and reasoning complete.

    Flow:
        Investigation report -> Suggested verification checks -> User approval -> SafeSQLValidator -> evidence execution.

    Safety:
        This object only describes checks. SQL execution still goes through SafeSQLValidator and never runs write
        statements or stored procedures.
    """

    claim: str
    verification_sql: str
    expected_result: str
    risk_level: str
    source: str
    status: str = "Pending"
    notes: str = ""
    purpose: str = ""
    claim_being_verified: str = ""
    evidence_logic: str = ""
    expected_result_explanation: str = ""
    interpretation: str = ""
    conclusion_template: str = ""

    def __post_init__(self) -> None:
        """
        Owner: Mukesh Dabi
        Purpose:
            Internal helper for post init within evidence_verification_agent.py.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Internal callers in evidence_verification_agent.py.
        
        Where it fits in the flow:
            Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
        
        Safety considerations:
            Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
        """
        defaults = _default_check_explanations(self.claim, self.verification_sql, self.expected_result, self.source)
        for field_name, value in defaults.items():
            if not getattr(self, field_name):
                object.__setattr__(self, field_name, value)


@dataclass(frozen=True)
class VerificationResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Captures the result of a user-approved verification check.

    Input:
        The approved SQL, expected result, actual result summary, status, and user who ran the check.

    Output:
        Auditable verification result shown in UI and appended to regenerated reports.

    Called by:
        execute_verification_check() from the /chat verification endpoints.

    Flow:
        User clicks Run -> SafeSQLValidator -> read-only query execution -> VerificationResult -> report regeneration.

    Safety:
        Results are produced only after validation allows SELECT, SHOW, DESCRIBE, DESC, or EXPLAIN.
    """

    claim: str
    verification_sql: str
    expected_result: str
    actual_result_summary: str
    status: str
    confidence_impact: str
    notes: str
    timestamp: str = ""
    verified_by: str = ""
    purpose: str = ""
    claim_being_verified: str = ""
    evidence_logic: str = ""
    expected_result_explanation: str = ""
    interpretation: str = ""
    conclusion_template: str = ""

    def __post_init__(self) -> None:
        """
        Owner: Mukesh Dabi
        Purpose:
            Internal helper for post init within evidence_verification_agent.py.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Internal callers in evidence_verification_agent.py.
        
        Where it fits in the flow:
            Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
        
        Safety considerations:
            Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
        """
        defaults = _default_check_explanations(self.claim, self.verification_sql, self.expected_result, "verification result")
        for field_name, value in defaults.items():
            if not getattr(self, field_name):
                object.__setattr__(self, field_name, value)


def suggest_verification_checks(
    *,
    question: str,
    intent: InvestigationIntent,
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    evidence_focus: EvidenceFocus | None,
    evidence_gate: EvidenceGateResult | None,
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
    reasoning: ReasoningResult,
) -> list[SuggestedVerificationCheck]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Builds the checklist of read-only verification checks that a human can approve after an investigation.

    Input:
        User question, detected intent, metadata, collected SQL evidence, evidence gate, procedure analysis,
        retrieved documents, and reasoning output.

    Output:
        SuggestedVerificationCheck items with safe SQL and plain-English explanation fields.

    Called by:
        The main /chat/ask orchestration flow after report reasoning has completed.

    Flow:
        Evidence package -> reasoning -> suggested verification checks -> UI approval workflow.

    Safety:
        This function suggests SQL only. The SQL is validated again before any execution and never bypasses the
        SafeSQLValidator.
    """

    checks: list[SuggestedVerificationCheck] = []
    if evidence_focus:
        checks.append(_suggest_affected_object(metadata, evidence_focus))
        parent_check = _suggest_parent_object(evidence, evidence_focus)
        if parent_check:
            checks.append(parent_check)
    if evidence_gate:
        gate_check = _suggest_gate(evidence, evidence_gate)
        if gate_check:
            checks.append(gate_check)
    duplicate_check = _suggest_reported_duplicate(question, intent, evidence)
    if duplicate_check:
        checks.append(duplicate_check)
    missing_check = _suggest_reported_missing(intent, evidence)
    if missing_check:
        checks.append(missing_check)
    if evidence_focus:
        writer_check = _suggest_direct_writer(evidence_focus, procedure_analysis)
        if writer_check:
            checks.append(writer_check)
        execution_check = _suggest_execution_path(evidence_focus, evidence)
        if execution_check:
            checks.append(execution_check)
    fix_check = _suggest_recommended_fix(reasoning, evidence_focus, procedure_analysis, documents)
    if fix_check:
        checks.append(fix_check)
    checks.append(_suggest_proof_sql_is_read_only(evidence))
    return checks


def execute_verification_check(
    *,
    connector,
    claim: str,
    verification_sql: str,
    expected_result: str,
    source: str,
    verified_by: str,
) -> list[VerificationResult]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Executes one human-approved verification check through the read-only safety validator.

    Input:
        Database connector, claim, verification SQL, expected result, source, and verifier identity.

    Output:
        A VerificationResult containing status, actual result summary, confidence impact, and audit context.

    Called by:
        /chat/verification-checks/{check_id}/run and /chat/investigations/{id}/verification-checks/run-all.

    Flow:
        User approval -> SafeSQLValidator -> connector.execute_read_only_query -> result comparison.

    Safety:
        Only SELECT, SHOW, DESCRIBE, DESC, and EXPLAIN statements are allowed. Stored procedures and write
        operations are rejected.
    """

    rows, error = _run_verification_sql(connector, verification_sql)
    status = _status_from_expected(expected_result, rows, error)
    return [
        VerificationResult(
            claim=claim,
            verification_sql=verification_sql,
            expected_result=expected_result,
            actual_result_summary=_summary(rows, error),
            status=status,
            confidence_impact=_impact(status),
            notes=f"Source: {source}. Executed only after human approval.",
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            verified_by=verified_by,
            conclusion_template=_conclusion_for_status(status, claim, _summary(rows, error)),
        )
    ]


def run_evidence_verification(
    *,
    connector,
    question: str,
    intent: InvestigationIntent,
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    evidence_focus: EvidenceFocus | None,
    evidence_gate: EvidenceGateResult | None,
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
    reasoning: ReasoningResult,
) -> list[VerificationResult]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles run evidence verification within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    results: list[VerificationResult] = []
    for check in suggest_verification_checks(
        question=question,
        intent=intent,
        metadata=metadata,
        evidence=evidence,
        evidence_focus=evidence_focus,
        evidence_gate=evidence_gate,
        procedure_analysis=procedure_analysis,
        documents=documents,
        reasoning=reasoning,
    ):
        results.extend(
            execute_verification_check(
                connector=connector,
                claim=check.claim,
                verification_sql=check.verification_sql,
                expected_result=check.expected_result,
                source=check.source,
                verified_by="system",
            )
        )
    return results


def adjust_confidence_with_verification(confidence: float, results: list[VerificationResult]) -> tuple[float, list[str]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles adjust confidence with verification within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    adjusted = confidence
    notes: list[str] = []
    for result in results:
        if result.status == "Verified":
            adjusted += 0.02
            notes.append(f"+ Verification passed: {result.claim}")
        elif result.status == "Partially Verified":
            adjusted -= 0.01
            notes.append(f"- Verification partial: {result.claim}")
        elif result.status == "Not Verified":
            adjusted -= 0.07
            notes.append(f"- Verification failed: {result.claim}")
        elif result.status == "Not Enough Evidence":
            adjusted = min(adjusted, 0.65)
            notes.append(f"- Verification limited by missing evidence: {result.claim}")
    return max(0.05, min(0.98, adjusted)), notes


def _suggest_affected_object(metadata: MetadataSearchResult, evidence_focus: EvidenceFocus) -> SuggestedVerificationCheck:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest affected object within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    table = next((table for table in metadata.tables if table.name.lower() == evidence_focus.affected_object.lower()), None)
    sql = f"DESCRIBE {evidence_focus.affected_object}" if table else "SELECT 'affected object not present in metadata' AS verification_note"
    return SuggestedVerificationCheck(
        claim=f"{evidence_focus.affected_object} is the affected object.",
        verification_sql=sql,
        expected_result="Rows returned",
        risk_level="Read-only",
        source="metadata",
        notes=evidence_focus.affected_object_reason,
    )


def _suggest_parent_object(evidence: list[EvidenceResult], evidence_focus: EvidenceFocus) -> SuggestedVerificationCheck | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest parent object within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    parent_table = _parent_table_from_evidence(evidence)
    if not parent_table:
        return None
    candidate = next(
        (
            item
            for item in evidence
            if parent_table in item.sql.lower()
            and evidence_focus.affected_object.lower() in item.sql.lower()
            and re.search(r"\bjoin\b", item.sql, re.I)
        ),
        None,
    )
    return SuggestedVerificationCheck(
        claim=f"{parent_table} is the parent/supporting object for {evidence_focus.affected_object}.",
        verification_sql=candidate.sql if candidate else f"DESCRIBE {parent_table}",
        expected_result="Rows returned",
        risk_level="Read-only",
        source="SQL evidence",
        notes="Parent object is inferred from parent-child join evidence.",
    )


def _suggest_gate(evidence: list[EvidenceResult], evidence_gate: EvidenceGateResult) -> SuggestedVerificationCheck | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest gate within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    candidate = next((item for item in evidence if item.rows), None)
    if candidate is None:
        return None
    return SuggestedVerificationCheck(
        claim="Reported condition passes the evidence gate.",
        verification_sql=candidate.sql,
        expected_result="Rows returned",
        risk_level="Read-only",
        source="SQL evidence",
        notes="Verifies that live evidence still returns rows for the reported condition.",
    )


def _suggest_reported_duplicate(
    question: str,
    intent: InvestigationIntent,
    evidence: list[EvidenceResult],
) -> SuggestedVerificationCheck | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest reported duplicate within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if intent not in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION}:
        return None
    candidate = next((item for item in evidence if "duplicate" in item.purpose.lower() and "having count" in item.sql.lower()), None)
    if candidate is None:
        return None
    expected = "Rows returned"
    if re.search(r"\b(active|open)\b", question, re.I):
        expected = "Rows returned with status/state evidence"
    return SuggestedVerificationCheck(
        claim="Duplicate condition is reproduced by live database evidence.",
        verification_sql=candidate.sql,
        expected_result=expected,
        risk_level="Read-only",
        source="SQL evidence",
        notes="Re-runs the duplicate-condition SQL after human approval.",
    )


def _suggest_reported_missing(intent: InvestigationIntent, evidence: list[EvidenceResult]) -> SuggestedVerificationCheck | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest reported missing within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if intent != InvestigationIntent.MISSING_DATA:
        return None
    candidate = next((item for item in evidence if item.purpose == "Confirmed Missing Related Record Candidates"), None)
    if candidate is None:
        return None
    return SuggestedVerificationCheck(
        claim="Missing related record condition is reproduced by live database evidence.",
        verification_sql=candidate.sql,
        expected_result="Rows returned",
        risk_level="Read-only",
        source="SQL evidence",
        notes="Re-runs the missing-record candidate SQL after human approval.",
    )


def _suggest_direct_writer(
    evidence_focus: EvidenceFocus,
    procedure_analysis: list[ProcedureAnalysis],
) -> SuggestedVerificationCheck | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest direct writer within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    top_writer = next((rank for rank in evidence_focus.ranked_procedures if rank.writes_affected_object), None)
    if not top_writer:
        return None
    return SuggestedVerificationCheck(
        claim=f"{top_writer.procedure} writes {evidence_focus.affected_object}.",
        verification_sql=(
            "SELECT routine_name, routine_definition "
            "FROM information_schema.routines "
            f"WHERE routine_name = '{top_writer.procedure.replace(chr(39), chr(39) + chr(39))}'"
        ),
        expected_result=f"Rows returned containing {evidence_focus.affected_object}",
        risk_level="Read-only",
        source="procedure",
        notes="Procedure text is inspected with a read-only information_schema query; no procedure execution is allowed.",
    )


def _suggest_execution_path(evidence_focus: EvidenceFocus, evidence: list[EvidenceResult]) -> SuggestedVerificationCheck | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest execution path within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if not evidence_focus.ranked_procedures:
        return None
    log_candidate = next(
        (item for item in evidence if any(term in f"{item.purpose} {item.sql}".lower() for term in ("error", "log", "job", "audit", "history"))),
        None,
    )
    if log_candidate:
        sql = log_candidate.sql
        expected = "Rows returned"
    else:
        sql = "SELECT 'job/error/audit evidence was not collected' AS verification_note"
        expected = "Metadata-only partial verification"
    return SuggestedVerificationCheck(
        claim="Exact execution path is supported by live operational evidence.",
        verification_sql=sql,
        expected_result=expected,
        risk_level="Read-only",
        source="SQL evidence",
        notes="Without job/error/audit rows this check can only be partially verified.",
    )


def _suggest_recommended_fix(
    reasoning: ReasoningResult,
    evidence_focus: EvidenceFocus | None,
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
) -> SuggestedVerificationCheck | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest recommended fix within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    fix_text = " ".join(reasoning.recommended_fix + [claim.conclusion for claim in reasoning.likely_root_causes]).lower()
    if not any(term in fix_text for term in ("exists", "idempot", "unique", "duplicate", "guard")):
        return None
    writer_name = evidence_focus.ranked_procedures[0].procedure if evidence_focus and evidence_focus.ranked_procedures else ""
    sql = (
        "SELECT routine_name, routine_definition "
        "FROM information_schema.routines "
        f"WHERE routine_name = '{writer_name.replace(chr(39), chr(39) + chr(39))}'"
        if writer_name
        else "SELECT 'no direct writer was confirmed' AS verification_note"
    )
    return SuggestedVerificationCheck(
        claim="Recommended fix is consistent with collected evidence.",
        verification_sql=sql,
        expected_result="Rows returned",
        risk_level="Read-only",
        source="procedure" if writer_name else "metadata",
        notes="Checks whether procedure text can support idempotency, uniqueness, or guard-condition recommendations.",
    )


def _suggest_proof_sql_is_read_only(evidence: list[EvidenceResult]) -> SuggestedVerificationCheck:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggest proof sql is read only within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    sql_count = len(evidence)
    return SuggestedVerificationCheck(
        claim="Proof and investigation SQL are valid read-only statements.",
        verification_sql=f"SELECT {sql_count} AS generated_read_only_sql_statement_count",
        expected_result="Rows returned",
        risk_level="Read-only",
        source="metadata",
        notes="The server validates SQL again immediately before execution.",
    )


def _verify_affected_object(
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    evidence_focus: EvidenceFocus,
) -> VerificationResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify affected object within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    affected = evidence_focus.affected_object
    table_exists = any(table.name.lower() == affected.lower() for table in metadata.tables)
    evidence_mentions = any(affected.lower() in f"{item.purpose} {item.sql}".lower() for item in evidence)
    status = "Verified" if table_exists and evidence_mentions else "Partially Verified" if table_exists else "Not Verified"
    return VerificationResult(
        claim=f"{affected} is the affected object.",
        verification_sql="Metadata and collected SQL evidence check",
        expected_result="Affected object exists in metadata and appears in evidence SQL.",
        actual_result_summary=f"metadata_match={table_exists}; evidence_mentions_object={evidence_mentions}",
        status=status,
        confidence_impact=_impact(status),
        notes=evidence_focus.affected_object_reason,
    )


def _verify_parent_object(evidence: list[EvidenceResult], evidence_focus: EvidenceFocus) -> VerificationResult | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify parent object within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    parent_table = _parent_table_from_evidence(evidence)
    if not parent_table:
        return None
    joined_rows = any(item.rows and parent_table in item.sql.lower() and evidence_focus.affected_object.lower() in item.sql.lower() for item in evidence)
    status = "Verified" if joined_rows else "Partially Verified"
    return VerificationResult(
        claim=f"{parent_table} is the parent/supporting object for {evidence_focus.affected_object}.",
        verification_sql="Existing parent-child JOIN evidence",
        expected_result="Parent and affected child object appear in returned join evidence.",
        actual_result_summary=f"parent={parent_table}; join_rows_returned={joined_rows}",
        status=status,
        confidence_impact=_impact(status),
        notes="Parent object was inferred from returned parent-child join SQL, not from a domain-specific rule.",
    )


def _verify_gate(evidence_gate: EvidenceGateResult) -> VerificationResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify gate within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    status = "Verified" if evidence_gate.reproduced else "Not Verified"
    if evidence_gate.required and not evidence_gate.reproduced and evidence_gate.confirmed_facts:
        status = "Partially Verified"
    return VerificationResult(
        claim="Reported condition passes the evidence gate.",
        verification_sql="Evidence gate checks over returned read-only SQL rows",
        expected_result="Business key, affected rows, reported condition, and relationship are supported.",
        actual_result_summary=(
            f"business_key={evidence_gate.business_key_exists}; condition={evidence_gate.reported_condition_exists}; "
            f"affected_rows={evidence_gate.affected_rows_exist}; relationship={evidence_gate.parent_child_relationship_exists}"
        ),
        status=status,
        confidence_impact=_impact(status),
        notes="; ".join(evidence_gate.confirmed_facts or evidence_gate.blocking_reasons),
    )


def _verify_reported_duplicate(
    connector,
    question: str,
    intent: InvestigationIntent,
    evidence: list[EvidenceResult],
) -> VerificationResult | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify reported duplicate within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if intent not in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION}:
        return None
    candidate = next((item for item in evidence if "duplicate" in item.purpose.lower() and "having count" in item.sql.lower()), None)
    if candidate is None:
        return None
    rows, error = _run_verification_sql(connector, candidate.sql)
    expected = "Rows returned"
    status = _row_status(rows, error)
    if re.search(r"\b(active|open)\b", question, re.I) and rows and not _rows_have_status_values(rows):
        status = "Partially Verified"
    return VerificationResult(
        claim="Duplicate condition is reproduced by live database evidence.",
        verification_sql=candidate.sql,
        expected_result=expected,
        actual_result_summary=_summary(rows, error),
        status=status,
        confidence_impact=_impact(status),
        notes="Re-ran duplicate verification SQL through the read-only validator.",
    )


def _verify_reported_missing(connector, intent: InvestigationIntent, evidence: list[EvidenceResult]) -> VerificationResult | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify reported missing within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if intent != InvestigationIntent.MISSING_DATA:
        return None
    candidate = next((item for item in evidence if item.purpose == "Confirmed Missing Related Record Candidates"), None)
    if candidate is None:
        return None
    rows, error = _run_verification_sql(connector, candidate.sql)
    status = _row_status(rows, error)
    return VerificationResult(
        claim="Missing related record condition is reproduced by live database evidence.",
        verification_sql=candidate.sql,
        expected_result="Rows returned",
        actual_result_summary=_summary(rows, error),
        status=status,
        confidence_impact=_impact(status),
        notes="Re-ran missing-record verification SQL through the read-only validator.",
    )


def _verify_direct_writer(
    evidence_focus: EvidenceFocus,
    procedure_analysis: list[ProcedureAnalysis],
) -> VerificationResult | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify direct writer within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    top_writer = next((rank for rank in evidence_focus.ranked_procedures if rank.writes_affected_object), None)
    if not top_writer:
        return VerificationResult(
            claim=f"A selected stored procedure writes {evidence_focus.affected_object}.",
            verification_sql="Stored procedure metadata analysis",
            expected_result=f"At least one analyzed procedure writes {evidence_focus.affected_object}.",
            actual_result_summary="No analyzed procedure was confirmed to write the affected object.",
            status="Not Enough Evidence",
            confidence_impact=_impact("Not Enough Evidence"),
            notes="Procedure-write root causes remain unconfirmed without procedure metadata.",
        )
    analysis = next((item for item in procedure_analysis if item.name == top_writer.procedure), None)
    writes = bool(analysis and _contains_table(analysis.tables_written, evidence_focus.affected_object))
    status = "Verified" if writes else "Not Verified"
    return VerificationResult(
        claim=f"{top_writer.procedure} writes {evidence_focus.affected_object}.",
        verification_sql="Stored procedure analysis tables_written metadata",
        expected_result=f"Procedure analysis lists {evidence_focus.affected_object} in tables_written.",
        actual_result_summary=f"tables_written={', '.join(analysis.tables_written) if analysis else 'not analyzed'}",
        status=status,
        confidence_impact=_impact(status),
        notes="No stored procedure execution was performed.",
    )


def _verify_execution_path(evidence_focus: EvidenceFocus) -> VerificationResult | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify execution path within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if not evidence_focus.ranked_procedures:
        return None
    top = evidence_focus.ranked_procedures[0]
    diagnostic_support = contains_diagnostic_reference(top.evidence_found)
    if top.error_log_support or top.job_history_support or diagnostic_support:
        status = "Verified"
        summary = "Job/error evidence supports the selected execution path."
    elif top.writes_affected_object:
        status = "Partially Verified"
        summary = "Direct writer is confirmed, but job/error/audit timing evidence is missing."
    else:
        status = "Not Enough Evidence"
        summary = "No direct writer or job/error/audit support was confirmed."
    return VerificationResult(
        claim="Exact execution path is supported by live operational evidence.",
        verification_sql="Error-log, job-history, audit-log, and procedure-ranking evidence",
        expected_result="Logs or job history reference the selected writer and affected object.",
        actual_result_summary=summary,
        status=status,
        confidence_impact=_impact(status),
        notes=f"Top ranked procedure: {top.procedure}; evidence={'; '.join(top.evidence_found)}",
    )


def _verify_recommended_fix(
    reasoning: ReasoningResult,
    evidence_focus: EvidenceFocus | None,
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
) -> VerificationResult | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify recommended fix within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    fix_text = " ".join(reasoning.recommended_fix + [claim.conclusion for claim in reasoning.likely_root_causes]).lower()
    if not any(term in fix_text for term in ("exists", "idempot", "unique", "duplicate", "guard")):
        return None
    writer_name = evidence_focus.ranked_procedures[0].procedure if evidence_focus and evidence_focus.ranked_procedures else ""
    writer = next((item for item in procedure_analysis if item.name == writer_name), None)
    doc_support = bool(documents)
    missing_guards = bool(
        writer and (writer.missing_exists_checks or writer.missing_uniqueness_checks)
    )
    proc_support = bool(writer and (missing_guards or writer.tables_written))
    status = (
        "Verified"
        if proc_support and missing_guards
        else "Partially Verified"
        if proc_support or doc_support
        else "Not Enough Evidence"
    )
    return VerificationResult(
        claim="Recommended fix is consistent with collected evidence.",
        verification_sql="Procedure analysis and retrieved document evidence",
        expected_result="Procedure/write-path or documents support idempotency, uniqueness, or guard-condition recommendation.",
        actual_result_summary=f"procedure_support={proc_support}; document_support={doc_support}",
        status=status,
        confidence_impact=_impact(status),
        notes="This verifies recommendation support only; it does not apply or test a fix.",
    )


def _verify_proof_sql_is_read_only(evidence: list[EvidenceResult]) -> VerificationResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verify proof sql is read only within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    errors: list[str] = []
    for item in evidence:
        try:
            validate_read_only_sql(item.sql)
        except Exception as exc:
            errors.append(f"{item.purpose}: {exc}")
    status = "Verified" if not errors else "Not Verified"
    return VerificationResult(
        claim="Proof and investigation SQL are valid read-only statements.",
        verification_sql="SafeSQLValidator over generated SQL",
        expected_result="Only SELECT, SHOW, DESCRIBE, DESC, or EXPLAIN statements are allowed.",
        actual_result_summary="All generated SQL passed read-only validation." if not errors else "; ".join(errors[:3]),
        status=status,
        confidence_impact=_impact(status),
        notes="The verification agent did not execute writes or stored procedures.",
    )


def _default_check_explanations(claim: str, sql: str, expected_result: str, source: str) -> dict[str, str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for default check explanations within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    claim_l = claim.lower()
    sql_l = sql.lower()
    if "parent/supporting object" in claim_l or re.search(r"\bjoin\b", sql_l):
        purpose = (
            "Confirms that the supplied business key is being investigated through the discovered parent-child "
            "relationship instead of by searching the child object with the parent key."
        )
        evidence_logic = (
            "The read-only SQL follows the discovered relationship path, usually by joining the parent table to "
            "the affected child table and counting or listing related child rows."
        )
        expected_explanation = (
            "Rows returned support the relationship path. More than one related child row can also support a "
            "duplicate condition when the claim is about duplicates."
        )
        interpretation = (
            "Row returned with matching child rows means the relationship is supported. A single child row means "
            "the parent exists but a duplicate is not proven. No rows means the parent key or relationship path "
            "was not reproduced from the connected database."
        )
    elif "duplicate" in claim_l or "having count" in sql_l:
        purpose = "Confirms that the reported duplicate condition can be reproduced from live read-only evidence."
        evidence_logic = "The SQL groups candidate records by the inferred business key or relationship and returns rows only when duplicate counts are present."
        expected_explanation = "Rows returned mean the duplicate condition is supported. No rows means the duplicate was not reproduced from current data."
        interpretation = "Look for count columns greater than one and matching business keys. Status columns explain whether duplicates are active/open or historical."
    elif "missing" in claim_l:
        purpose = "Confirms that the reported missing-record condition can be reproduced from live read-only evidence."
        evidence_logic = "The SQL uses discovered relationships, usually a parent-to-child left join, to find parent records where the expected child record is absent."
        expected_explanation = "Rows returned mean missing candidates exist. No rows means the missing-record condition was not reproduced from current data."
        interpretation = "Review the parent key, child key, status, and issue-type columns to decide whether the missing record is confirmed or needs more evidence."
    elif "writes" in claim_l or "routine_definition" in sql_l or "procedure" in source.lower():
        purpose = "Confirms whether the selected stored procedure is supported by procedure metadata for this claim."
        evidence_logic = "The SQL reads metadata or procedure definitions and looks for evidence that the procedure references or writes the affected object."
        expected_explanation = "Rows returned with the affected object or routine definition support the procedure claim. Missing rows limit or reject the claim."
        interpretation = "A matching procedure definition supports the write-path hypothesis. No matching procedure metadata means the procedure claim needs more evidence."
    elif "proof" in claim_l or "read-only" in claim_l:
        purpose = "Confirms that generated proof and investigation SQL remains read-only."
        evidence_logic = "The system validates generated SQL with SafeSQLValidator and summarizes the number of allowed statements."
        expected_explanation = "Rows returned indicate the validation summary was produced. Validator errors mean unsafe SQL was blocked."
        interpretation = "This check protects production systems; it does not prove the business root cause by itself."
    elif "evidence gate" in claim_l or "reported condition" in claim_l:
        purpose = "Confirms that root-cause analysis is based on a reported condition reproduced from live evidence."
        evidence_logic = "The SQL reuses collected evidence that returned rows for the key, affected object, relationship, or reported condition."
        expected_explanation = "Rows returned support continuing root-cause analysis. No rows means the issue was not reproduced and fixes should not be recommended."
        interpretation = "Use this result to decide whether the investigation can make a supported conclusion or must remain low confidence."
    else:
        purpose = "Verifies an investigation claim with human-approved read-only SQL."
        evidence_logic = "The SQL is executed against the connected database after validation and compared with the expected result."
        expected_explanation = f"Expected result: {expected_result}."
        interpretation = "Rows returned generally support the claim when the expected result asks for rows; no rows or errors reduce confidence."
    return {
        "purpose": purpose,
        "claim_being_verified": claim,
        "evidence_logic": evidence_logic,
        "expected_result_explanation": expected_explanation,
        "interpretation": interpretation,
        "conclusion_template": (
            "After execution, the app marks this claim Verified, Partially Verified, Not Verified, or Not Enough "
            "Evidence based on the actual result and the expected result."
        ),
    }


def _conclusion_for_status(status: str, claim: str, summary: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for conclusion for status within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if status == "Verified":
        return f"Verified because the approved read-only check returned evidence supporting the claim: {claim}. Result summary: {summary}"
    if status == "Partially Verified":
        return f"Partially verified because the check returned some supporting evidence, but not enough to prove the full claim: {claim}. Result summary: {summary}"
    if status == "Not Verified":
        return f"Not verified because the approved read-only check did not reproduce evidence for the claim: {claim}. Result summary: {summary}"
    return f"Not enough evidence because the approved read-only check could not fully evaluate the claim: {claim}. Result summary: {summary}"


def _run_verification_sql(connector, sql: str) -> tuple[list[dict[str, Any]], str | None]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for run verification sql within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    try:
        validate_read_only_sql(sql)
        return connector.execute_read_only_query(sql, limit=25), None
    except Exception as exc:
        return [], str(exc)


def _row_status(rows: list[dict[str, Any]], error: str | None) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for row status within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if error:
        return "Not Enough Evidence"
    return "Verified" if rows else "Not Verified"


def _status_from_expected(expected_result: str, rows: list[dict[str, Any]], error: str | None) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for status from expected within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if error:
        return "Not Enough Evidence"
    expected_l = expected_result.lower()
    if "metadata-only partial" in expected_l:
        return "Partially Verified" if rows else "Not Enough Evidence"
    contains_match = re.search(r"containing\s+([a-zA-Z0-9_]+)", expected_result, re.I)
    if contains_match:
        if not rows:
            return "Not Enough Evidence"
        needle = contains_match.group(1).lower()
        row_text = " ".join(str(value) for row in rows for value in row.values()).lower()
        return "Verified" if needle in row_text else "Partially Verified"
    if "status/state" in expected_l and rows:
        return "Verified" if _rows_have_status_values(rows) else "Partially Verified"
    if "rows returned" in expected_l:
        return "Verified" if rows else "Not Verified"
    return "Verified" if rows else "Not Enough Evidence"


def _summary(rows: list[dict[str, Any]], error: str | None) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for summary within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if error:
        return f"Verification query failed: {error}"
    if not rows:
        return "No rows returned."
    preview = rows[0]
    return f"{len(rows)} row(s) returned; first row: {preview}"


def _impact(status: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for impact within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    return {
        "Verified": "Increases confidence",
        "Partially Verified": "Slightly limits confidence",
        "Not Verified": "Decreases confidence",
        "Not Enough Evidence": "Caps confidence until more evidence is available",
    }.get(status, "No confidence impact")


def _parent_table_from_evidence(evidence: list[EvidenceResult]) -> str | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for parent table from evidence within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    for item in evidence:
        if not re.search(r"\bjoin\b", item.sql, re.I):
            continue
        match = re.search(r"\bfrom\s+([`\"\[\]\w.]+)\s+p\b", item.sql, re.I)
        if match:
            return str(match.group(1)).strip("`[]\"").split(".")[-1].lower()
    return None


def _rows_have_status_values(rows: list[dict[str, Any]]) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for rows have status values within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    return any(any("status" in key.lower() or "state" in key.lower() for key in row) for row in rows)


def _contains_table(tables: list[str], table: str) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for contains table within evidence_verification_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_verification_agent.py.
    
    Where it fits in the flow:
        Investigation report -> suggested checks -> user approval -> safe execution -> verification result.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    target = table.lower().strip("`[]\"").split(".")[-1]
    return any(value.lower().strip("`[]\"").split(".")[-1] == target for value in tables)
