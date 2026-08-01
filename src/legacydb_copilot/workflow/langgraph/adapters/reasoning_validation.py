from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from legacydb_copilot.services.claim_verification_service import (
    build_evidence_registry,
    parse_structured_claim,
    verify_claim,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.workflow.langgraph.enums import (
    EvidenceOutcome,
    WorkflowReasoningMode,
)
from legacydb_copilot.workflow.langgraph.state import ClaimEvidenceLink, InvestigationState


@dataclass(frozen=True)
class ReasoningValidationAdapter:
    load_evidence: Callable[[tuple[str, ...]], list[EvidenceResult]]

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        if not state["reasoning_result"]:
            return {
                "reasoning_claim_validations": [],
                "reasoning_validation_errors": [],
            }
        evidence = self.load_evidence(tuple(state["verified_evidence_ids"]))
        registry = build_evidence_registry(evidence)
        raw_claims = state["reasoning_result"].get("claims") or []
        validations = []
        accepted = []
        links: list[ClaimEvidenceLink] = []
        errors: list[str] = []
        for index, raw in enumerate(raw_claims, 1):
            claim = parse_structured_claim(raw, index)
            if claim is None:
                errors.append(f"CL-{index:03d}: INVALID_CLAIM_SCHEMA")
                continue
            verification = verify_claim(claim, registry)
            semantic_error = _semantic_error(claim.statement, state)
            result = verification.to_dict()
            if semantic_error:
                result["verification_result"] = "REJECTED"
                result["rejection_code"] = semantic_error
            validations.append(result)
            if result["verification_result"] in {"VERIFIED", "EVIDENCE_GAP"}:
                accepted.append(raw)
                links.append(
                    ClaimEvidenceLink(
                        claim_id=claim.claim_id,
                        evidence_ids=tuple(result["evidence_ids_resolved"]),
                    )
                )
            else:
                errors.append(f"{claim.claim_id}: {result.get('rejection_code')}")
        sanitized_result = dict(state["reasoning_result"])
        sanitized_result["claims"] = accepted
        update: dict[str, Any] = {
            "reasoning_result": sanitized_result,
            "reasoning_claim_validations": validations,
            "reasoning_validation_errors": errors,
            "claim_evidence_links": links,
        }
        if errors:
            update.update(
                {
                    "reasoning_mode": WorkflowReasoningMode.NEEDS_HUMAN_REVIEW,
                    "quality_review_required": True,
                    "reasoning_warnings": [*state["reasoning_warnings"], *errors],
                }
            )
        return update


def _semantic_error(statement: str, state: InvestigationState) -> str:
    normalized = statement.casefold()
    findings = {item.finding_type for item in state["findings"]}
    if EvidenceOutcome.CALCULATION_NOT_POSSIBLE in findings and (
        "age is" in normalized or "years old" in normalized
    ):
        return "NULL_VALUE_HALLUCINATION"
    if EvidenceOutcome.NO_MATCHING_ROW in findings and (
        "null" in normalized or "dateofbirth" in normalized
    ):
        return "NO_ROW_MISCLASSIFIED_AS_NULL"
    if "foreign key" in normalized and any(
        edge.verification.value == "INFERRED" for edge in state["relationship_edges"]
    ):
        return "INFERRED_RELATIONSHIP_UPGRADED"
    if "procedure executed" in normalized and any(
        item.inspection_only for item in state["selected_objects"]
    ):
        return "PROCEDURE_INSPECTION_MISREPRESENTED"
    if "proof of fix" in normalized and not state["reproduction_evidence_ids"]:
        return "UNSUPPORTED_PROOF_OF_FIX"
    return ""
