from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import StrEnum

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.services.diagnostic_object_service import contains_diagnostic_reference
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
class MissingEvidence:
    evidence_type: str
    description: str
    related_entity: str
    reason_required: str


@dataclass(frozen=True, eq=False)
class RootCauseClaim:
    conclusion: str
    evidence_refs: list[str] = field(default_factory=list)
    status: RootCauseSupportStatus = RootCauseSupportStatus.NOT_EVALUATED
    missing_evidence: list[MissingEvidence] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", RootCauseSupportStatus(self.status))

    def __str__(self) -> str:
        if self.evidence_refs:
            return f"{self.conclusion} Evidence: {', '.join(self.evidence_refs)}."
        return self.conclusion

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        if isinstance(other, RootCauseClaim):
            return (
                self.conclusion,
                self.evidence_refs,
                self.status,
                self.missing_evidence,
            ) == (
                other.conclusion,
                other.evidence_refs,
                other.status,
                other.missing_evidence,
            )
        return NotImplemented

    def __contains__(self, value: str) -> bool:
        return value in self.conclusion


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


def evaluate_claim_support_status(
    claim: RootCauseClaim,
    evidence_records: list[EvidenceResult],
) -> RootCauseClaim:
    validation = validate_claim_evidence_references(claim, evidence_records)
    if not validation.valid_evidence_refs and not validation.missing_evidence_refs:
        status = RootCauseSupportStatus.NOT_EVALUATED
    elif validation.valid_evidence_refs and not validation.missing_evidence_refs:
        status = RootCauseSupportStatus.VERIFIED
    elif validation.valid_evidence_refs:
        status = RootCauseSupportStatus.PARTIALLY_SUPPORTED
    else:
        status = RootCauseSupportStatus.UNSUPPORTED
    return replace(claim, status=status)


def build_deterministic_root_cause_claim(
    conclusion: str,
    evidence_refs: object = None,
    evidence_records: list[EvidenceResult] | None = None,
) -> RootCauseClaim | None:
    normalized_conclusion = str(conclusion or "").strip()
    if not normalized_conclusion:
        return None
    candidates: list[object]
    if isinstance(evidence_refs, str):
        candidates = [evidence_refs]
    elif isinstance(evidence_refs, list | tuple):
        candidates = list(evidence_refs)
    else:
        candidates = []
    normalized_refs = [ref.strip() for ref in candidates if isinstance(ref, str) and ref.strip()]
    claim = RootCauseClaim(conclusion=normalized_conclusion, evidence_refs=normalized_refs)
    return evaluate_claim_support_status(claim, evidence_records or [])


@dataclass(frozen=True)
class ReasoningResult:
    summary: str
    likely_root_causes: list[RootCauseClaim]
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
    response_type: str = "multiple_possible_causes"

    def __post_init__(self) -> None:
        claims = [
            item if isinstance(item, RootCauseClaim) else RootCauseClaim(conclusion=str(item))
            for item in self.likely_root_causes
        ]
        object.__setattr__(self, "likely_root_causes", claims)


def finalize_evidence_backed_response_type(
    reasoning: ReasoningResult,
    *,
    reproduced: bool,
    evidence_required: bool,
    rejected_claim_count: int = 0,
    unresolved_contradiction_count: int = 0,
    execution_failure_count: int = 0,
) -> ReasoningResult:
    """Derive the public response type from verified terminal evidence signals."""
    verified_claims = [
        claim
        for claim in reasoning.likely_root_causes
        if claim.status is RootCauseSupportStatus.VERIFIED
    ]
    if unresolved_contradiction_count or execution_failure_count:
        response_type = "insufficient_evidence"
    elif reproduced and verified_claims:
        response_type = "confirmed_root_cause"
    elif reproduced and (evidence_required or rejected_claim_count):
        response_type = "insufficient_evidence"
    elif evidence_required and not reproduced:
        response_type = "evidence_summary_not_reproduced"
    else:
        return reasoning
    return replace(reasoning, response_type=response_type)


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


def _supports_failed_downstream_generation(item: EvidenceResult) -> bool:
    if not item.rows or not contains_diagnostic_reference((item.purpose, item.sql)):
        return False
    failure_terms = ("absent", "failed", "failure", "missing", "not generated", "not created")
    return any(
        term in " ".join(str(value) for value in row.values()).casefold()
        for row in item.rows
        for term in failure_terms
    )


def _diagnostic_causal_finding(
    question: str,
    evidence: list[EvidenceResult],
) -> tuple[str, list[str]] | None:
    """Build a cited causal finding from explicit operational failure details."""
    causal_request = any(
        term in question.casefold()
        for term in ("why", "root cause", "caused", "failed", "failure", "retry")
    )
    if not causal_request:
        return None
    detail_markers = ("error", "message", "reason", "detail", "description", "status")
    findings: list[str] = []
    refs: list[str] = []
    for item in evidence:
        if not _supports_failed_downstream_generation(item):
            continue
        row_findings: list[str] = []
        for row in item.rows:
            details = [
                f"{column}={value}"
                for column, value in row.items()
                if value not in (None, "")
                and any(marker in str(column).casefold() for marker in detail_markers)
            ]
            if details:
                row_findings.append(", ".join(details))
        if row_findings:
            findings.extend(row_findings[:2])
            refs.append(item.evidence_id)
    if not findings:
        return None
    return (
        "Operational diagnostic evidence identifies the failed workflow condition: "
        + "; ".join(dict.fromkeys(findings)),
        _diagnostic_evidence_refs(evidence, refs),
    )


def _diagnostic_evidence_refs(
    evidence: list[EvidenceResult],
    diagnostic_refs: list[str],
) -> list[str]:
    """Return the verified evidence chain for a downstream diagnostic cause."""
    accepted_purposes = {
        "Verify upstream entity and current transition status",
        "Confirmed Missing Related Record Candidates",
    }
    diagnostic_ref_set = set(diagnostic_refs)
    refs: list[str] = []
    for item in evidence:
        is_relevant_chain_item = (
            item.purpose in accepted_purposes
            or item.evidence_id in diagnostic_ref_set
        )
        if (
            not is_relevant_chain_item
            or item.execution_status != "succeeded"
            or item.error
            or not item.rows
            or item.evidence_relevance == "irrelevant"
        ):
            continue
        if item.evidence_id not in refs:
            refs.append(item.evidence_id)
    return refs


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


def _verified_null_fields(
    evidence: list[EvidenceResult],
) -> dict[str, list[str]]:
    """Return nullable fields proved NULL by successful, relevant row evidence."""
    null_fields: dict[str, list[str]] = {}
    for item in evidence:
        if (
            item.execution_status != "succeeded"
            or item.error
            or item.evidence_semantics != "null_value"
            or item.evidence_relevance == "irrelevant"
            or not item.rows
        ):
            continue
        for row in item.rows:
            for column, value in row.items():
                if value is None:
                    null_fields.setdefault(str(column), []).append(item.evidence_id)
    return {
        column: list(dict.fromkeys(refs))
        for column, refs in null_fields.items()
    }


def _causally_relevant_null_fields(
    question: str,
    null_fields: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Limit NULL-driven conclusions to fields implicated by the request."""
    normalized_question = re.sub(r"[^a-z0-9]+", "", question.casefold())
    explicit_null_request = any(
        marker in question.casefold()
        for marker in (" null", "missing value", "not populated", "not set")
    )
    calculation_aliases = {
        "age": {"birthdate", "dateofbirth", "dob"},
    }
    requested_aliases = {
        alias
        for request_term, aliases in calculation_aliases.items()
        if request_term in question.casefold()
        for alias in aliases
    }
    return {
        column: refs
        for column, refs in null_fields.items()
        if explicit_null_request
        or re.sub(r"[^a-z0-9]+", "", column.casefold()) in normalized_question
        or re.sub(r"[^a-z0-9]+", "", column.casefold()) in requested_aliases
    }


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
    diagnostic_evidence = [
        item for item in non_empty if _supports_failed_downstream_generation(item)
    ]
    diagnostic_cause = _diagnostic_causal_finding(question, evidence)
    response_type = "multiple_possible_causes"
    supporting = [f"{item.evidence_type} - {item.subject}: {item.finding}" for item in correlated_evidence if item.confidence in {"High", "Medium"}]
    if not supporting:
        supporting = [f"{item.purpose}: {len(item.rows)} row(s) returned" for item in non_empty]
    missing = [f"{item.purpose}: {item.error or 'no rows returned'}" for item in evidence if not item.rows]
    root_causes: list[str] = []
    root_cause_refs: dict[str, list[str]] = {}
    verified_nulls = _verified_null_fields(evidence)
    causal_nulls = _causally_relevant_null_fields(question, verified_nulls)
    null_findings = [
        f"{column} is verified as NULL. Evidence: {', '.join(refs)}."
        for column, refs in verified_nulls.items()
    ]
    for column, refs in verified_nulls.items():
        supporting.append(
            f"Verified finding: {column} is NULL. Evidence: {', '.join(refs)}."
        )
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
    if causal_nulls:
        response_type = "inconclusive_verified_null"
    elif diagnostic_cause:
        response_type = "confirmed_root_cause"
        conclusion, refs = diagnostic_cause
        root_causes.append(conclusion)
        root_cause_refs[conclusion] = refs
    elif duplicate_like:
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
            if diagnostic_evidence:
                response_type = "confirmed_root_cause"
                confirmed = (
                    "The required downstream work item was not created after the completed "
                    "upstream transition; operational diagnostic evidence records the missing "
                    "or failed downstream generation."
                )
                root_causes.append(confirmed)
                root_cause_refs[confirmed] = list(
                    dict.fromkeys(
                        [
                            *(
                                item.evidence_id
                                for item in evidence
                                if item.rows
                                and item.purpose
                                in {
                                    "Verify upstream entity and current transition status",
                                    "Confirmed Missing Related Record Candidates",
                                }
                            ),
                            *(item.evidence_id for item in diagnostic_evidence),
                        ]
                    )
                )
            else:
                root_causes.extend([
                    "MISSING_RELATED_RECORD: expected child or related records are missing for parent records based on discovered metadata relationships.",
                    "parent_not_eligible or parent_status_not_ready: evaluate returned parent status/state columns and documented eligibility rules.",
                    "procedure_failed or batch_failed: only supported if error-log, job-history, or procedure evidence references the affected relationship.",
                    "duplicate_or_blocking_child_object: only supported if returned child rows show duplicate/blocking candidates for the same parent relationship.",
                    "dependency_missing: only supported when upstream foreign-key or dependency rows are absent from evidence.",
                    "unknown/evidence_missing: use this group when the missing child is confirmed but no write-path, status, job, or log evidence proves the cause.",
                ])
        else:
            response_type = "insufficient_evidence"
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
    if intent.intent == InvestigationIntent.MISSING_DATA and _rows_for_purpose(
        evidence, "Confirmed Missing Related Record Candidates"
    ):
        fix = [
            (
                "Correct the evidenced workflow condition or exception before completing "
                "the approved transactional downstream workflow."
            ),
            (
                "Before replay or regeneration, verify that no downstream item exists under "
                "the expected key or another correlation identifier and confirm the operation "
                "is idempotent."
            ),
            (
                "Do not manually insert business records; use the validated workflow with "
                "change approval, rollback planning, and duplicate checks."
            ),
        ]
    if causal_nulls:
        field_list = ", ".join(causal_nulls)
        ref_text = ", ".join(
            dict.fromkeys(ref for refs in causal_nulls.values() for ref in refs)
        )
        fix = [
            (
                f"Entering valid source data for {field_list}, through the approved data "
                f"process after source verification, is a prerequisite for any dependent "
                f"calculation. No change has been executed. Evidence: {ref_text}."
            ),
            (
                "Verify the data origin and validation path before proposing a corrective "
                "change; the current evidence does not establish why the value is NULL."
            ),
        ]
    proof_of_fix = ["Run proof SQL after the fix; expected result depends on the failure type and should show no duplicate/missing/failed condition remains."]
    if causal_nulls:
        proof_of_fix = [
            "No fix was executed or proved. After an approved change, rerun the same "
            "read-only evidence query and the dependent calculation as separate checks."
        ]
    if intent.intent == InvestigationIntent.MISSING_DATA and _rows_for_purpose(evidence, "Confirmed Missing Related Record Candidates"):
        proof_of_fix = [
            "Verify the affected parent record still exists and has the expected business/status state.",
            "Verify the expected related child record now exists for the parent using the same relationship columns.",
            "Verify the missing-related-record proof query returns zero rows for the affected key or scope.",
            "Verify no new relevant error-log or job-history failure rows were created after the fix, when those logs are available.",
        ]
    missing_evidence = missing or ["No obvious missing evidence from executed read-only checks."]
    if causal_nulls:
        missing_evidence = [
            "The evidence verifies the NULL value but does not establish its origin.",
            "Dependent behavior cannot be concluded unless its definition or "
            "execution result is verified.",
        ]
    if intent.intent == InvestigationIntent.MISSING_DATA and _rows_for_purpose(evidence, "Confirmed Missing Related Record Candidates"):
        missing_evidence = missing or [
            "Check the write procedure or job definition to confirm the exact guard condition that creates the child record.",
            "Check recent error-log, audit-log, or job-history rows after the attempted fix.",
        ]
    requested_calculation = (
        "age calculation"
        if re.search(r"\bage\b", question, re.I)
        else "requested calculation"
    )
    summary = (
        "Verified findings: database evidence contains one or more NULL source values. "
        f"Interpretation: the {requested_calculation} cannot be completed without its "
        "required valid input. Evidence gap: the origin of the NULL and any downstream "
        "root cause remain unproven."
        if causal_nulls
        else (
            "Investigation generated dynamically from detected intent, extracted "
            "entities, ranked database objects, stored procedure analysis, retrieved "
            "documents, approved knowledge, and safe SQL evidence."
        )
    )
    return ReasoningResult(
        summary=summary,
        likely_root_causes=[
            claim
            for item in root_causes
            if item.strip()
            if (
                claim := build_deterministic_root_cause_claim(
                    item,
                    root_cause_refs.get(item, []),
                    evidence,
                )
            )
            is not None
        ],
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
        confirmed_facts=list(
            dict.fromkeys(
                [
                    *(evidence_focus.confirmed_facts if evidence_focus else supporting),
                    *null_findings,
                ]
            )
        ),
        inferred_findings=evidence_focus.inferred_findings if evidence_focus else root_causes,
        hypotheses=evidence_focus.hypotheses if evidence_focus else root_causes,
        response_type=response_type,
    )
