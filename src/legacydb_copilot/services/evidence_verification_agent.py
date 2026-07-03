from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import ReasoningResult
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus, ProcedureRank
from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.safe_sql_service import validate_read_only_sql
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


@dataclass(frozen=True)
class VerificationResult:
    claim: str
    verification_sql: str
    expected_result: str
    actual_result_summary: str
    status: str
    confidence_impact: str
    notes: str


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
    results: list[VerificationResult] = []
    if evidence_focus:
        results.append(_verify_affected_object(metadata, evidence, evidence_focus))
        parent_result = _verify_parent_object(evidence, evidence_focus)
        if parent_result:
            results.append(parent_result)
    if evidence_gate:
        results.append(_verify_gate(evidence_gate))
    duplicate_result = _verify_reported_duplicate(connector, question, intent, evidence)
    if duplicate_result:
        results.append(duplicate_result)
    missing_result = _verify_reported_missing(connector, intent, evidence)
    if missing_result:
        results.append(missing_result)
    if evidence_focus:
        writer_result = _verify_direct_writer(evidence_focus, procedure_analysis)
        if writer_result:
            results.append(writer_result)
        execution_result = _verify_execution_path(evidence_focus)
        if execution_result:
            results.append(execution_result)
    fix_result = _verify_recommended_fix(reasoning, evidence_focus, procedure_analysis, documents)
    if fix_result:
        results.append(fix_result)
    results.append(_verify_proof_sql_is_read_only(evidence))
    return results


def adjust_confidence_with_verification(confidence: float, results: list[VerificationResult]) -> tuple[float, list[str]]:
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


def _verify_affected_object(
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    evidence_focus: EvidenceFocus,
) -> VerificationResult:
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
    if not evidence_focus.ranked_procedures:
        return None
    top = evidence_focus.ranked_procedures[0]
    if top.error_log_support or top.job_history_support:
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
    fix_text = " ".join(reasoning.recommended_fix + reasoning.likely_root_causes).lower()
    if not any(term in fix_text for term in ("exists", "idempot", "unique", "duplicate", "guard")):
        return None
    writer_name = evidence_focus.ranked_procedures[0].procedure if evidence_focus and evidence_focus.ranked_procedures else ""
    writer = next((item for item in procedure_analysis if item.name == writer_name), None)
    doc_support = bool(documents)
    proc_support = bool(writer and (writer.missing_exists_checks or writer.missing_uniqueness_checks or writer.tables_written))
    status = "Verified" if proc_support and (writer.missing_exists_checks or writer.missing_uniqueness_checks) else "Partially Verified" if proc_support or doc_support else "Not Enough Evidence"
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


def _run_verification_sql(connector, sql: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        validate_read_only_sql(sql)
        return connector.execute_read_only_query(sql, limit=25), None
    except Exception as exc:
        return [], str(exc)


def _row_status(rows: list[dict[str, Any]], error: str | None) -> str:
    if error:
        return "Not Enough Evidence"
    return "Verified" if rows else "Not Verified"


def _summary(rows: list[dict[str, Any]], error: str | None) -> str:
    if error:
        return f"Verification query failed: {error}"
    if not rows:
        return "No rows returned."
    preview = rows[0]
    return f"{len(rows)} row(s) returned; first row: {preview}"


def _impact(status: str) -> str:
    return {
        "Verified": "Increases confidence",
        "Partially Verified": "Slightly limits confidence",
        "Not Verified": "Decreases confidence",
        "Not Enough Evidence": "Caps confidence until more evidence is available",
    }.get(status, "No confidence impact")


def _parent_table_from_evidence(evidence: list[EvidenceResult]) -> str | None:
    for item in evidence:
        if not re.search(r"\bjoin\b", item.sql, re.I):
            continue
        match = re.search(r"\bfrom\s+([`\"\[\]\w.]+)\s+p\b", item.sql, re.I)
        if match:
            return str(match.group(1)).strip("`[]\"").split(".")[-1].lower()
    return None


def _rows_have_status_values(rows: list[dict[str, Any]]) -> bool:
    return any(any("status" in key.lower() or "state" in key.lower() for key in row) for row in rows)


def _contains_table(tables: list[str], table: str) -> bool:
    target = table.lower().strip("`[]\"").split(".")[-1]
    return any(value.lower().strip("`[]\"").split(".")[-1] == target for value in tables)
