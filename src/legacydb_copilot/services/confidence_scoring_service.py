from __future__ import annotations

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument


def score_confidence(
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None = None,
) -> float:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles score confidence within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    score = 0.2
    row_results = [item for item in evidence if item.rows]
    empty_results = [item for item in evidence if not item.rows and not item.error]
    error_results = [item for item in evidence if item.error]
    if row_results:
        score += min(0.35, 0.08 * len(row_results))
    if empty_results:
        score += min(0.12, 0.02 * len(empty_results))
    if any("EXPLAIN" in item.sql.upper() for item in evidence):
        score += 0.08
    if evidence_focus and evidence_focus.affected_object != "Not determined":
        score += 0.12
    if evidence_focus and evidence_focus.inferred_business_key:
        score += 0.08
    if evidence_focus and any(item.writes_affected_object for item in evidence_focus.ranked_procedures):
        score += 0.12
    elif metadata.procedures:
        score -= 0.04
    if documents:
        score += 0.04
    if evidence_focus and any("execution evidence is still needed" in item for item in evidence_focus.hypotheses):
        score -= 0.08
    if error_results:
        score -= min(0.2, 0.06 * len(error_results))
    return round(max(0.1, min(score, 0.95)), 2)


def confidence_factors(
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None = None,
) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles confidence factors within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    factors: list[str] = []
    row_results = [item for item in evidence if item.rows]
    empty_results = [item for item in evidence if not item.rows and not item.error]
    error_results = [item for item in evidence if item.error]
    if row_results:
        factors.append(f"+ {len(row_results)} evidence query result(s) returned rows.")
    if empty_results:
        factors.append(f"+ {len(empty_results)} read-only query result(s) returned no rows and ruled out alternatives.")
    if any("EXPLAIN" in item.sql.upper() for item in evidence):
        factors.append("+ EXPLAIN or execution-plan evidence was collected.")
    if evidence_focus and evidence_focus.affected_object != "Not determined":
        factors.append(f"+ Affected object identified from question and evidence: {evidence_focus.affected_object}.")
    if evidence_focus and evidence_focus.inferred_business_key:
        factors.append(f"+ Business key inferred from metadata/evidence: {evidence_focus.inferred_business_key}.")
    if evidence_focus and any(item.writes_affected_object for item in evidence_focus.ranked_procedures):
        writer = next(item.procedure for item in evidence_focus.ranked_procedures if item.writes_affected_object)
        factors.append(f"+ Stored procedure metadata confirms a direct writer: {writer}.")
    elif metadata.procedures:
        factors.append("- Stored procedures exist, but no direct writer was confirmed for the affected object.")
    if documents:
        factors.append("+ Uploaded documents or approved knowledge were available for business interpretation.")
    if evidence_focus and any("execution evidence is still needed" in item for item in evidence_focus.hypotheses):
        factors.append("- Job, audit, or execution timing evidence is still missing.")
    if error_results:
        factors.append(f"- {len(error_results)} evidence query result(s) failed or were unavailable.")
    if not factors:
        factors.append("- Confidence is low because no strong evidence factors were available.")
    return factors
