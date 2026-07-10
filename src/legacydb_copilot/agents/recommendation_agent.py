from __future__ import annotations

from dataclasses import dataclass

from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import ReasoningResult
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence


@dataclass(frozen=True)
class RecommendationResult:
    immediate_fix: list[str]
    permanent_fix: list[str]
    future_improvement: list[str]
    estimated_effort: str
    risk: str
    business_impact: str
    monitoring: list[str]
    modernization: list[str]


def recommend_actions(
    *,
    intent: InvestigationIntent,
    reasoning: ReasoningResult,
    correlated_evidence: list[CorrelatedEvidence],
) -> RecommendationResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles recommend actions within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation orchestration in routers/chat.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    evidence_ref = _evidence_reference(correlated_evidence)
    has_write_proc = any("writes" in item.finding.lower() and "writes 0" not in item.finding.lower() for item in correlated_evidence)
    has_sql_errors = any(item.evidence_type == "SQL" and item.confidence == "Low" for item in correlated_evidence)
    immediate = [f"Validate the top-ranked root cause with the recommended read-only SQL before making changes. Evidence: {evidence_ref}."]
    permanent = [f"Apply the smallest approved schema/procedure/configuration change that directly addresses the confirmed cause. Evidence: {evidence_ref}."]
    future = [f"Add this incident to the human-approved knowledge base after DBA/lead review. Evidence: approved feedback workflow."]
    effort = "Medium"
    risk = "Medium"
    impact = "Business impact depends on affected rows and process criticality; confirm with process owner."
    monitoring = ["Alert on recurrence of the failed condition and on increased duration/error count for related jobs."]
    modernization = ["Document procedure dependencies and add automated regression checks for the affected workflow."]

    if intent == InvestigationIntent.PERFORMANCE_INVESTIGATION:
        immediate = [f"Capture EXPLAIN output and confirm whether the slow path is full scan, filesort, temp table, blocking, or missing index. Evidence: {evidence_ref}."]
        permanent = [f"Add or adjust indexes and rewrite predicates only after validating before/after plans. Evidence: {evidence_ref}."]
        future.append(f"Archive or partition historical rows only if volume is a confirmed contributor. Evidence: {evidence_ref}.")
        monitoring.append(f"Track query duration, rows scanned, and plan changes for the affected statement. Evidence: {evidence_ref}.")
        impact = "Slow processing can delay downstream business operations and batch completion."
    elif intent in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION} and any("duplicate" in cause.conclusion.lower() for cause in reasoning.likely_root_causes):
        immediate = [f"Stop repeat processing for the affected key until duplicate evidence and insert source are confirmed. Evidence: {evidence_ref}."]
        permanent = [f"Make the write path idempotent and add uniqueness protection where business rules allow it. Evidence: {evidence_ref}."]
        monitoring.append(f"Alert when duplicate business keys or repeated retry attempts appear. Evidence: {evidence_ref}.")
        impact = "Duplicate records can cause repeated downstream actions, inaccurate reporting, reconciliation issues, or user-facing errors."
    elif intent == InvestigationIntent.MISSING_DATA:
        has_missing_related_candidates = any(item.subject == "Confirmed Missing Related Record Candidates" and "row(s) returned" in item.finding for item in correlated_evidence)
        if has_missing_related_candidates:
            immediate = [
                f"Confirm the affected parent record, relationship columns, and missing child record using the generated read-only SQL. Evidence: {evidence_ref}.",
                f"Rerun or trigger the approved downstream creation workflow only after the upstream state and guard conditions are verified. Evidence: {evidence_ref}.",
            ]
            permanent = [
                f"Fix the procedure, job, or workflow branch that fails to create the expected related record. Evidence: {evidence_ref}.",
                f"Add explicit logging when guard conditions block downstream record creation. Evidence: {evidence_ref}.",
            ]
            future.append(f"Add a dashboard check for parent records that remain without their expected child records, grouped by discovered relationship and issue type. Evidence: {evidence_ref}.")
            monitoring.append(f"Alert on recurring missing-related-record candidates for the affected relationship. Evidence: {evidence_ref}.")
            monitoring.append(f"Alert when source records remain in ready/complete states without downstream child records beyond the expected SLA. Evidence: {evidence_ref}.")
            impact = "Missing related records can block the affected business workflow, reporting, reconciliation, or downstream automation."
        else:
            immediate = [f"Confirm the upstream record/status and the missing downstream record using proof SQL. Evidence: {evidence_ref}."]
            permanent = [f"Fix the guard condition, status transition, or procedure branch that prevents downstream creation. Evidence: {evidence_ref}."]
            monitoring.append(f"Alert when source records stay in ready/complete status without downstream records. Evidence: {evidence_ref}.")
            impact = "Missing records can block fulfillment, invoicing, reporting, or reconciliation."
    elif intent == InvestigationIntent.FAILED_BATCH_JOB:
        immediate = [f"Identify the failed job step, error row, related procedure, and affected business keys. Evidence: {evidence_ref}."]
        permanent = [f"Fix the failing dependency and add retry controls that are idempotent. Evidence: {evidence_ref}."]
        monitoring.append(f"Alert on failed job steps and duration increases against SLA. Evidence: {evidence_ref}.")
        impact = "Batch failures can delay downstream processing and operational reporting."
    elif intent == InvestigationIntent.PROCESS_FLOW_BREAK:
        immediate = [f"Trace current status at each discovered process step and identify the first broken transition. Evidence: {evidence_ref}."]
        permanent = [f"Correct the transition rule or procedure branch and add regression tests around the flow. Evidence: {evidence_ref}."]
        monitoring.append(f"Alert when records remain in intermediate statuses beyond the expected threshold. Evidence: {evidence_ref}.")

    if has_write_proc:
        risk = "High"
        future.append(f"Review transaction boundaries and locking behavior in write procedures. Evidence: {evidence_ref}.")
    if has_sql_errors:
        future.append("Grant metadata/read privileges needed for complete investigation evidence.")
    if reasoning.likely_root_causes and (
        reasoning.likely_root_causes[0].conclusion.startswith("Could not confirm")
        or reasoning.likely_root_causes[0].conclusion.startswith("Reported issue could not be reproduced")
    ):
        immediate = ["No fix recommended until read-only evidence reproduces the reported condition."]
        permanent = ["Collect the missing key, relationship, affected-row, and condition evidence before changing schema, data, procedures, or jobs."]
        monitoring = ["Track this investigation as evidence-blocked until reproduction SQL returns confirming rows."]
        effort = "Unknown until missing evidence is collected"
        risk = "Unknown"

    return RecommendationResult(
        immediate_fix=immediate,
        permanent_fix=permanent,
        future_improvement=future,
        estimated_effort=effort,
        risk=risk,
        business_impact=impact,
        monitoring=monitoring,
        modernization=modernization,
    )


def _evidence_reference(correlated_evidence: list[CorrelatedEvidence]) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for evidence reference within recommendation_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in recommendation_agent.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    for item in correlated_evidence:
        if item.confidence in {"High", "Medium"}:
            return f"{item.evidence_type} - {item.subject}"
    return "collected evidence and missing-evidence list"
