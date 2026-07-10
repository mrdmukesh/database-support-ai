from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


class RootCauseSupportStatus(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    VERIFIED = "VERIFIED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


@dataclass(frozen=True)
class RootCauseClaim:
    conclusion: str
    evidence_refs: list[str] = field(default_factory=list)
    status: RootCauseSupportStatus = RootCauseSupportStatus.NOT_EVALUATED

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", RootCauseSupportStatus(self.status))


@dataclass(frozen=True)
class ClaimEvidenceValidationResult:
    is_valid: bool
    missing_evidence_refs: list[str]
    valid_evidence_refs: list[str]


def validate_claim_evidence_references(
    claim: RootCauseClaim,
    evidence_records: list[EvidenceResult],
) -> ClaimEvidenceValidationResult:
    available_ids = {record.evidence_id for record in evidence_records}
    unique_refs = list(dict.fromkeys(ref for ref in claim.evidence_refs if ref))
    valid_refs = [ref for ref in unique_refs if ref in available_ids]
    missing_refs = [ref for ref in unique_refs if ref not in available_ids]
    return ClaimEvidenceValidationResult(
        is_valid=not missing_refs,
        missing_evidence_refs=missing_refs,
        valid_evidence_refs=valid_refs,
    )


@dataclass(frozen=True)
class ReasoningResult:
    summary: str
    likely_root_causes: list[str]
    supporting_evidence: list[str]
    missing_evidence: list[str]
    recommended_fix: list[str]
    test_cases: list[dict[str, str]]
    proof_of_fix: list[str]
    rollback_plan: list[str]
    risks: list[str]
    confirmed_facts: list[str] = field(default_factory=list)
    inferred_findings: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)


def _rows_for_purpose(evidence: list[EvidenceResult], purpose: str) -> list[dict]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for rows for purpose within reasoning_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in reasoning_agent.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    return next((item.rows for item in evidence if item.purpose == purpose), [])


def _issue_counts(rows: list[dict]) -> dict[str, int]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for issue counts within reasoning_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in reasoning_agent.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    counts: dict[str, int] = {}
    for row in rows:
        issue_type = str(row.get("issue_type") or "")
        if issue_type:
            counts[issue_type] = counts.get(issue_type, 0) + 1
    return counts


def _has_explain_or_row_estimate(evidence: list[EvidenceResult]) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for has explain or row estimate within reasoning_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in reasoning_agent.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    for item in evidence:
        text = f"{item.purpose} {item.sql}".upper()
        if "EXPLAIN" in text and (item.rows or item.error is None):
            return True
        if item.rows and any(any("rows" in str(key).lower() for key in row) for row in item.rows):
            return True
    return False


def reason_about_evidence(
    question: str,
    intent: IntentResult,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    documents: list[RetrievedDocument],
    correlated_evidence: list[CorrelatedEvidence] | None = None,
    procedure_analysis: list[ProcedureAnalysis] | None = None,
    evidence_focus: EvidenceFocus | None = None,
) -> ReasoningResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles reason about evidence within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation orchestration in routers/chat.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    correlated_evidence = correlated_evidence or []
    procedure_analysis = procedure_analysis or []
    non_empty = [item for item in evidence if item.rows]
    supporting = [f"{item.evidence_type} - {item.subject}: {item.finding}" for item in correlated_evidence if item.confidence in {"High", "Medium"}]
    if not supporting:
        supporting = [f"{item.purpose}: {len(item.rows)} row(s) returned" for item in non_empty]
    missing = [f"{item.purpose}: {item.error or 'no rows returned'}" for item in evidence if not item.rows]
    root_causes: list[str] = []
    if evidence_focus:
        write_procs = [
            proc
            for proc in procedure_analysis
            if any(rank.procedure == proc.name and rank.writes_affected_object for rank in evidence_focus.ranked_procedures)
        ]
    else:
        write_procs = [proc for proc in procedure_analysis if proc.tables_written]
    complex_procs = [proc for proc in procedure_analysis if proc.complexity == "High" or proc.locking_risk == "High"]
    duplicate_like = intent.intent in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION} and any(
        "duplicate" in item.purpose.lower() or (item.rows and "duplicate" in item.sql.lower())
        for item in evidence
    )
    if duplicate_like:
        if evidence_focus and evidence_focus.confirmed_facts:
            duplicate_facts = [fact for fact in evidence_focus.confirmed_facts if " has " in fact and evidence_focus.affected_object in fact]
            root_causes.extend(duplicate_facts[:2])
        if write_procs:
            writer = write_procs[0]
            object_name = evidence_focus.affected_object if evidence_focus else "the affected object"
            writer_rank = next(
                (rank for rank in evidence_focus.ranked_procedures if rank.procedure == writer.name),
                None,
            ) if evidence_focus else None
            support = "; ".join((writer_rank.evidence_found if writer_rank else [])[:4]) or "Procedure Analysis tables_written"
            certainty = "Most likely" if writer_rank and (writer_rank.error_log_support or non_empty) else "Likely"
            root_causes.append(
                f"{certainty} write-path cause: {writer.name} may lack idempotency, uniqueness, retry, or transaction guards for {object_name}. Evidence: {support}."
            )
        elif evidence_focus:
            root_causes.append(f"No stored procedure was confirmed to write {evidence_focus.affected_object}; procedure-write root causes must remain unconfirmed until procedure metadata or logs prove a direct writer.")
        key_text = f" around business key {evidence_focus.inferred_business_key}" if evidence_focus and evidence_focus.inferred_business_key else ""
        root_causes.append(f"No uniqueness protection was confirmed to prevent multiple active records{key_text}. Evidence: metadata/index and duplicate evidence checks.")
        root_causes.append("Retry, job, or audit evidence is still needed to prove exact execution timing and triggering path. Evidence: missing error/job/audit support.")
    elif intent.intent == InvestigationIntent.PERFORMANCE_INVESTIGATION:
        if _has_explain_or_row_estimate(evidence):
            if complex_procs:
                root_causes.append(f"Procedure complexity or locking risk is supported by procedure evidence: {', '.join(proc.name for proc in complex_procs[:3])}.")
            root_causes.append("Performance root cause must be derived from EXPLAIN rows, row estimates, index usage, scan type, filesort/temp-table flags, or blocking evidence returned above.")
        else:
            root_causes.append("Performance issue was not confirmed because EXPLAIN or row-estimate evidence was not collected.")
    elif intent.intent == InvestigationIntent.MISSING_DATA:
        missing_related_rows = _rows_for_purpose(evidence, "Confirmed Missing Related Record Candidates")
        issue_counts = _issue_counts(missing_related_rows)
        if issue_counts:
            summary = ", ".join(f"{key}={value}" for key, value in sorted(issue_counts.items()))
            supporting.append(f"Confirmed Missing Related Record Candidates: {len(missing_related_rows)} row(s) found; issue counts: {summary}.")
            root_causes.extend(
                [
                    "MISSING_RELATED_RECORD: expected child or related records are missing for parent records based on discovered metadata relationships.",
                    "parent_not_eligible or parent_status_not_ready: evaluate returned parent status/state columns and documented eligibility rules.",
                    "procedure_failed or batch_failed: only supported if error-log, job-history, or procedure evidence references the affected relationship.",
                    "duplicate_or_blocking_child_object: only supported if returned child rows show duplicate/blocking candidates for the same parent relationship.",
                    "dependency_missing: only supported when upstream foreign-key or dependency rows are absent from evidence.",
                    "unknown/evidence_missing: use this group when the missing child is confirmed but no write-path, status, job, or log evidence proves the cause.",
                ]
            )
        else:
            if write_procs:
                root_causes.append(f"Downstream creation may be blocked by guard conditions in {', '.join(proc.name for proc in write_procs[:3])}.")
            root_causes.append("The expected downstream record was not confirmed; validate upstream status and procedure guard conditions.")
    elif intent.intent == InvestigationIntent.PROCESS_FLOW_BREAK:
        root_causes.append("Process-flow cause must be identified from execution-order procedure read/write evidence, returned status/state rows, validation rules, and the first unsupported transition.")
    elif intent.intent == InvestigationIntent.FAILED_BATCH_JOB:
        root_causes.append("Based on available evidence, use job history, batch status, and error-log rows to identify the failed step and related procedure.")
    else:
        root_causes.append("Based on available evidence, no single confirmed root cause was determined automatically.")
    if intent.intent == InvestigationIntent.IMPACT_ANALYSIS:
        root_causes = ["Impact analysis should enumerate every discovered procedure, view, report/query, job, document rule, test, and rollback dependency that references the proposed changed value."]
    if intent.intent == InvestigationIntent.HEALTH_ASSESSMENT:
        root_causes = ["Health assessment should score schema design, indexing/performance, stored procedures, data quality, batch processing, security, scalability, and maintainability separately with evidence for each score."]
    if not non_empty:
        root_causes = ["Could not confirm from available database metadata or documents."]
    if intent.intent == InvestigationIntent.MISSING_DATA and _rows_for_purpose(evidence, "Confirmed Missing Related Record Candidates"):
        missing = [item for item in missing if "Confirmed Missing Related Record Candidates" not in item]
    fix = [
        "Run the recommended SELECT/EXPLAIN queries and verify the evidence with a DBA. Evidence: SQL evidence plan.",
        "Apply the smallest safe fix after confirming the exact broken status, key, procedure, or plan. Evidence: confirmed facts and ranked hypotheses.",
        "Do not run write or DDL commands without change approval, rollback plan, and backup validation. Evidence: safety policy.",
    ]
    proof_of_fix = ["Run proof SQL after the fix; expected result depends on the failure type and should show no duplicate/missing/failed condition remains."]
    if intent.intent == InvestigationIntent.MISSING_DATA and _rows_for_purpose(evidence, "Confirmed Missing Related Record Candidates"):
        proof_of_fix = [
            "Verify the affected parent record still exists and has the expected business/status state.",
            "Verify the expected related child record now exists for the parent using the same relationship columns.",
            "Verify the missing-related-record proof query returns zero rows for the affected key or scope.",
            "Verify no new relevant error-log or job-history failure rows were created after the fix, when those logs are available.",
        ]
    missing_evidence = missing or ["No obvious missing evidence from executed read-only checks."]
    if intent.intent == InvestigationIntent.MISSING_DATA and _rows_for_purpose(evidence, "Confirmed Missing Related Record Candidates"):
        missing_evidence = missing or [
            "Check the write procedure or job definition to confirm the exact guard condition that creates the child record.",
            "Check recent error-log, audit-log, or job-history rows after the attempted fix.",
        ]
    return ReasoningResult(
        summary="Investigation generated dynamically from detected intent, extracted entities, ranked database objects, stored procedure analysis, retrieved documents, approved knowledge, and safe SQL evidence.",
        likely_root_causes=root_causes,
        supporting_evidence=supporting or ["No confirming rows were returned by the safe evidence plan."],
        missing_evidence=missing_evidence,
        recommended_fix=fix,
        test_cases=[
            {"Test ID": "TC-001", "Scenario": "Evidence validation", "Steps": "Run recommended SQL", "Expected Result": "Evidence matches report", "Actual Result": "Pending", "Status": "Pending"},
            {"Test ID": "TC-002", "Scenario": "Fix validation", "Steps": "Apply approved fix in lower environment and rerun proof SQL", "Expected Result": "Issue no longer reproduces", "Actual Result": "Pending", "Status": "Pending"},
        ],
        proof_of_fix=proof_of_fix,
        rollback_plan=["Capture before-state rows.", "Apply fix through versioned script or approved deployment.", "If validation fails, restore previous procedure/config/index state using the rollback script.", "Re-run proof SQL and attach output."],
        risks=["Business impact depends on the affected process and returned evidence.", "Technical risk increases if manual data repair is attempted without dependency checks."],
        confirmed_facts=evidence_focus.confirmed_facts if evidence_focus else supporting,
        inferred_findings=evidence_focus.inferred_findings if evidence_focus else root_causes,
        hypotheses=evidence_focus.hypotheses if evidence_focus else root_causes,
    )
