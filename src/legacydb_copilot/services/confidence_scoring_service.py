from __future__ import annotations

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument


def _verified_rows(evidence: list[EvidenceResult]) -> list[EvidenceResult]:
    return [
        item
        for item in evidence
        if item.execution_status == "succeeded"
        and not item.error
        and bool(item.rows)
        and item.evidence_relevance == "relevant"
        and item.evidence_semantics
        in {
            "positive_rows",
            "aggregate",
            "metadata",
            "null_value",
            "procedure_definition",
            "procedure_execution",
        }
        and bool(
            item.supports_claim
            or item.evidence_semantics
            in {
                "metadata",
                "procedure_definition",
                "procedure_execution",
            }
        )
    ]


def _verified_absences(evidence: list[EvidenceResult]) -> list[EvidenceResult]:
    return [
        item
        for item in evidence
        if item.execution_status == "succeeded"
        and not item.error
        and item.zero_row_result
        and item.evidence_semantics == "verified_absence"
        and item.evidence_relevance == "relevant"
        and bool(item.supports_claim)
    ]


def _claim_is_verified(claim: object) -> bool:
    status = str(getattr(claim, "status", "")).casefold()
    return status in {"verified", "rootcausesupportstatus.verified"}


def score_confidence(
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None = None,
    *,
    evidence_gate=None,
    reasoning=None,
    rejected_claim_count: int = 0,
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
        Application orchestration -> service function -> structured result for the
        next workflow step.

    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    score = 0.2
    row_results = _verified_rows(evidence)
    empty_results = _verified_absences(evidence)
    error_results = [
        item for item in evidence if item.execution_status != "succeeded" or item.error
    ]
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
    if evidence_focus and any(
        item.writes_affected_object for item in evidence_focus.ranked_procedures
    ):
        score += 0.12
    elif any(item.evidence_id.startswith("PROC-") and item.rows for item in evidence):
        score += 0.08
    elif metadata.procedures:
        score -= 0.04
    if documents:
        score += 0.04
    if evidence_focus and any(
        "execution evidence is still needed" in item for item in evidence_focus.hypotheses
    ):
        score -= 0.08
    if error_results:
        score -= min(0.2, 0.06 * len(error_results))
    claims = list(getattr(reasoning, "likely_root_causes", ()) or ())
    verified_claims = [item for item in claims if _claim_is_verified(item)]
    unsupported_claims = [item for item in claims if item not in verified_claims]
    if verified_claims:
        score += min(0.12, 0.04 * len(verified_claims))
    if unsupported_claims:
        score -= min(0.3, 0.1 * len(unsupported_claims))
    if rejected_claim_count:
        score -= min(0.3, 0.12 * rejected_claim_count)
        if not verified_claims:
            score = min(score, 0.4)
    if getattr(reasoning, "response_type", "") in {
        "insufficient_evidence",
        "evidence_gap_summary",
    }:
        score = min(score, 0.35)
    if evidence_gate is not None:
        if getattr(evidence_gate, "required", False) and not getattr(
            evidence_gate, "reproduced", False
        ):
            score = min(score, 0.35)
        if getattr(evidence_gate, "evidence_gaps", None):
            score -= min(0.15, 0.04 * len(evidence_gate.evidence_gaps))
        if getattr(evidence_gate, "required", False) and getattr(
            evidence_gate, "reproduced", False
        ) and not verified_claims:
            score = min(score, 0.4)
    return round(max(0.1, min(score, 0.95)), 2)


def confidence_factors(
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None = None,
    *,
    evidence_gate=None,
    reasoning=None,
    rejected_claim_count: int = 0,
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
        Application orchestration -> service function -> structured result for the
        next workflow step.

    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    factors: list[str] = []
    row_results = _verified_rows(evidence)
    empty_results = _verified_absences(evidence)
    error_results = [
        item for item in evidence if item.execution_status != "succeeded" or item.error
    ]
    if row_results:
        factors.append(f"+ {len(row_results)} evidence query result(s) returned rows.")
    if empty_results:
        factors.append(
            f"+ {len(empty_results)} read-only query result(s) returned no rows "
            "and ruled out alternatives."
        )
    if any("EXPLAIN" in item.sql.upper() for item in evidence):
        factors.append("+ EXPLAIN or execution-plan evidence was collected.")
    if evidence_focus and evidence_focus.affected_object != "Not determined":
        factors.append(
            "+ Affected object identified from question and evidence: "
            f"{evidence_focus.affected_object}."
        )
    if evidence_focus and evidence_focus.inferred_business_key:
        factors.append(
            "+ Business key inferred from metadata/evidence: "
            f"{evidence_focus.inferred_business_key}."
        )
    if evidence_focus and any(
        item.writes_affected_object for item in evidence_focus.ranked_procedures
    ):
        writer = next(
            item.procedure
            for item in evidence_focus.ranked_procedures
            if item.writes_affected_object
        )
        factors.append(f"+ Stored procedure metadata confirms a direct writer: {writer}.")
    elif any(item.evidence_id.startswith("PROC-") and item.rows for item in evidence):
        factors.append(
            "+ Stored procedure definition evidence confirms relevant calculation logic."
        )
    elif metadata.procedures:
        factors.append(
            "- Stored procedures exist, but no direct writer was confirmed for the affected object."
        )
    if documents:
        factors.append(
            "+ Uploaded documents or approved knowledge were available for business interpretation."
        )
    if evidence_focus and any(
        "execution evidence is still needed" in item for item in evidence_focus.hypotheses
    ):
        factors.append("- Job, audit, or execution timing evidence is still missing.")
    if error_results:
        factors.append(
            f"- {len(error_results)} evidence query result(s) failed or were unavailable."
        )
    ignored = len(evidence) - len(row_results) - len(empty_results) - len(error_results)
    if ignored:
        factors.append(
            f"- {ignored} result(s) were not counted because their relevance or "
            "claim semantics were unverified."
        )
    claims = list(getattr(reasoning, "likely_root_causes", ()) or ())
    verified_claims = [item for item in claims if _claim_is_verified(item)]
    unsupported_claims = [item for item in claims if item not in verified_claims]
    if verified_claims:
        factors.append(
            f"+ {len(verified_claims)} root-cause claim(s) passed evidence verification."
        )
    if unsupported_claims:
        factors.append(f"- {len(unsupported_claims)} root-cause claim(s) were not fully verified.")
    if rejected_claim_count:
        factors.append(
            f"- {rejected_claim_count} generated causal claim(s) failed verification."
        )
    if getattr(reasoning, "response_type", "") in {
        "insufficient_evidence",
        "evidence_gap_summary",
    }:
        factors.append("- Confidence is capped by the insufficient-evidence outcome.")
    if (
        evidence_gate is not None
        and getattr(evidence_gate, "required", False)
        and not getattr(evidence_gate, "reproduced", False)
    ):
        factors.append("- Confidence is capped because the reported condition was not reproduced.")
    for gap in getattr(evidence_gate, "evidence_gaps", ()) if evidence_gate is not None else ():
        factors.append(f"- Verified evidence gap: {gap}.")
    if not factors:
        factors.append("- Confidence is low because no strong evidence factors were available.")
    return factors
