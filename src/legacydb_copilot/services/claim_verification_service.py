from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis

VERIFIER_VERSION = "claim-evidence-v1"
_REFERENCE_FIELDS = (
    "evidence_ids",
    "evidence_refs",
    "citations",
    "sources",
    "supporting_evidence",
)


def normalize_evidence_id(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    text = str(value).strip().upper().replace("_", "-")
    match = re.fullmatch(r"([A-Z]+)-?0*(\d+)", text)
    return f"{match.group(1)}-{int(match.group(2))}" if match else text


@dataclass(frozen=True)
class EvidenceReference:
    evidence_id: str
    type: str
    title: str
    sql: str = ""
    columns: tuple[str, ...] = ()
    rows: tuple[dict[str, Any], ...] = ()
    row_count: int = 0
    zero_row_result: bool = False
    evidence_semantics: str = ""
    supports_claim: str = ""
    included_in_prompt: bool = True
    truncated: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    column_types: dict[str, str] = field(default_factory=dict)
    nullable_columns: tuple[str, ...] = ()
    exact_cardinality_result: str = ""
    entity_table: str = ""
    identifier_column: str = ""
    identifier_value: Any = None
    row_scope: str = ""

    def to_prompt_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["columns"] = list(self.columns)
        value["rows"] = list(self.rows)
        return value


@dataclass(frozen=True)
class StructuredClaim:
    claim_id: str
    statement: str
    claim_type: str
    evidence_ids: tuple[str, ...]
    evidence_gap: str | None = None
    recommended_action: str | None = None
    raw_claim: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimVerification:
    claim_id: str
    raw_claim_text: str
    parsed_claim: dict[str, Any]
    evidence_ids_requested: tuple[str, ...]
    evidence_ids_resolved: tuple[str, ...]
    verification_result: Literal["VERIFIED", "REJECTED", "EVIDENCE_GAP"]
    rejection_code: str = ""
    rejection_detail: str = ""
    contradictory_evidence_ids: tuple[str, ...] = ()
    verifier_version: str = VERIFIER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_registry(
    evidence: Iterable[EvidenceResult],
    procedures: Iterable[ProcedureAnalysis] = (),
    correlated: Iterable[CorrelatedEvidence] = (),
) -> list[EvidenceReference]:
    registry: list[EvidenceReference] = []
    for item in evidence:
        sample = tuple(dict(row) for row in item.rows[:5])
        columns = tuple(dict.fromkeys(key for row in sample for key in row))
        registry.append(
            EvidenceReference(
                evidence_id=normalize_evidence_id(item.evidence_id),
                type="SQL_RESULT" if item.sql else "COLLECTED_EVIDENCE",
                title=item.purpose,
                sql=item.sql,
                columns=columns,
                rows=sample,
                row_count=item.row_count,
                zero_row_result=item.zero_row_result,
                evidence_semantics=item.evidence_semantics,
                supports_claim=item.supports_claim,
                parameters=dict(item.parameters),
                column_types=dict(item.column_types),
                nullable_columns=tuple(item.nullable_columns),
                exact_cardinality_result=item.exact_cardinality_result,
                entity_table=item.entity_table,
                identifier_column=item.identifier_column,
                identifier_value=item.identifier_value,
                row_scope=item.row_scope,
            )
        )
    existing = {item.evidence_id for item in registry}
    for index, item in enumerate(procedures, start=1):
        evidence_id = normalize_evidence_id(f"PROC-{index}")
        if evidence_id in existing:
            continue
        registry.append(
            EvidenceReference(
                evidence_id=evidence_id,
                type="PROCEDURE_METADATA",
                title=f"Stored procedure {item.name}",
                columns=("name", "tables_read", "tables_written", "business_rules"),
                rows=(
                    {
                        "name": item.name,
                        "tables_read": item.tables_read,
                        "tables_written": item.tables_written,
                        "business_rules": item.business_rules,
                        "definition_excerpt": item.definition_excerpt[:1500],
                    },
                ),
                row_count=1,
            )
        )
    for index, item in enumerate(correlated, start=1):
        registry.append(
            EvidenceReference(
                evidence_id=normalize_evidence_id(f"EV-{index}"),
                type="CORRELATED_EVIDENCE",
                title=f"{item.evidence_type}: {item.subject}",
                columns=("subject", "finding", "support", "confidence"),
                rows=(
                    {
                        "subject": item.subject,
                        "finding": item.finding,
                        "support": item.support,
                        "confidence": item.confidence,
                    },
                ),
                row_count=1,
            )
        )
    return registry


def parse_structured_claim(raw_claim: Any, index: int = 1) -> StructuredClaim | None:
    if not isinstance(raw_claim, dict):
        return None
    statement = str(
        raw_claim.get("statement") or raw_claim.get("conclusion") or raw_claim.get("finding") or ""
    ).strip()
    evidence_gap = raw_claim.get("evidence_gap")
    if not statement and not evidence_gap:
        return None
    references: Any = None
    for field_name in _REFERENCE_FIELDS:
        if raw_claim.get(field_name) is not None:
            references = raw_claim[field_name]
            break
    if isinstance(references, (str, int)):
        references = [references]
    if not isinstance(references, (list, tuple)):
        references = []
    evidence_ids = tuple(
        dict.fromkeys(
            normalized for value in references if (normalized := normalize_evidence_id(value))
        )
    )
    claim_type = (
        str(
            raw_claim.get("claim_type")
            or ("EVIDENCE_GAP" if evidence_gap and not statement else "VERIFIED_FINDING")
        )
        .strip()
        .upper()
    )
    return StructuredClaim(
        claim_id=str(raw_claim.get("claim_id") or f"CL-{index:03d}"),
        statement=statement,
        claim_type=claim_type,
        evidence_ids=evidence_ids,
        evidence_gap=str(evidence_gap).strip() if evidence_gap else None,
        recommended_action=(
            str(raw_claim.get("recommended_action")).strip()
            if raw_claim.get("recommended_action")
            else None
        ),
        raw_claim=dict(raw_claim),
    )


def verify_claim(
    claim: StructuredClaim,
    registry: Iterable[EvidenceReference],
) -> ClaimVerification:
    references = {item.evidence_id: item for item in registry}
    resolved = tuple(ref for ref in claim.evidence_ids if ref in references)
    missing = tuple(ref for ref in claim.evidence_ids if ref not in references)
    parsed = {
        "claim_id": claim.claim_id,
        "statement": claim.statement,
        "claim_type": claim.claim_type,
        "evidence_ids": list(claim.evidence_ids),
        "evidence_gap": claim.evidence_gap,
        "recommended_action": claim.recommended_action,
    }
    base = {
        "claim_id": claim.claim_id,
        "raw_claim_text": claim.statement or claim.evidence_gap or "",
        "parsed_claim": parsed,
        "evidence_ids_requested": claim.evidence_ids,
        "evidence_ids_resolved": resolved,
    }
    if claim.claim_type == "EVIDENCE_GAP" and claim.evidence_gap:
        if missing:
            return ClaimVerification(
                **base,
                verification_result="REJECTED",
                rejection_code="EVIDENCE_ID_NOT_FOUND",
                rejection_detail=f"Unknown attempted evidence reference(s): {', '.join(missing)}",
            )
        return ClaimVerification(**base, verification_result="EVIDENCE_GAP")
    if not claim.evidence_ids:
        return ClaimVerification(
            **base,
            verification_result="REJECTED",
            rejection_code="MISSING_CITATIONS",
            rejection_detail="Factual claims require at least one evidence ID.",
        )
    if missing:
        return ClaimVerification(
            **base,
            verification_result="REJECTED",
            rejection_code="EVIDENCE_ID_NOT_FOUND",
            rejection_detail=f"Unknown evidence reference(s): {', '.join(missing)}",
        )
    prompted = [references[ref] for ref in resolved]
    truncated = tuple(
        item.evidence_id for item in prompted if item.truncated or not item.included_in_prompt
    )
    if truncated:
        return ClaimVerification(
            **base,
            verification_result="REJECTED",
            rejection_code="EVIDENCE_NOT_IN_PROMPT",
            rejection_detail=f"Evidence was truncated or not sent: {', '.join(truncated)}",
        )
    unverified_zero_rows = [
        item
        for item in prompted
        if item.zero_row_result and item.evidence_semantics != "verified_absence"
    ]
    if unverified_zero_rows:
        return ClaimVerification(
            **base,
            verification_result="REJECTED",
            rejection_code="UNVERIFIED_NEGATIVE_EVIDENCE",
            rejection_detail=(
                "A successful zero-row query is not absence evidence unless its "
                "scope and semantics are explicitly verified."
            ),
        )
    supporting = [item for item in prompted if _reference_supports_statement(claim.statement, item)]
    # Claims are checked against the complete evidence package, not only the
    # references selected by the claimant.  This prevents citation
    # cherry-picking from discarding conflicting collected evidence.
    claim_scopes = tuple(
        item for item in prompted if item.row_scope == "exact_entity" and _has_entity_scope(item)
    )
    contradictory = tuple(
        item.evidence_id
        for item in references.values()
        if item.included_in_prompt and not item.truncated
        if _eligible_contradiction(item, claim_scopes)
        if _reference_contradicts_statement(claim.statement, item)
    )
    if contradictory:
        return ClaimVerification(
            **base,
            verification_result="REJECTED",
            rejection_code="CONTRADICTORY_EVIDENCE",
            rejection_detail="Referenced evidence contradicts the claim.",
            contradictory_evidence_ids=contradictory,
        )
    if _unsupported_causal_explanation(claim.statement, prompted):
        return ClaimVerification(
            **base,
            verification_result="REJECTED",
            rejection_code="UNSUPPORTED_CAUSAL_EXPLANATION",
            rejection_detail=(
                "The cited evidence proves an observed value, not the asserted upstream cause."
            ),
        )
    if not supporting:
        return ClaimVerification(
            **base,
            verification_result="REJECTED",
            rejection_code="INSUFFICIENT_EVIDENCE_CONTENT",
            rejection_detail="Referenced evidence does not contain the columns and values needed.",
        )
    return ClaimVerification(**base, verification_result="VERIFIED")


def _has_entity_scope(evidence: EvidenceReference) -> bool:
    return bool(
        evidence.entity_table
        and evidence.identifier_column
        and evidence.identifier_value is not None
    )


def _matches_any_claim_scope(
    evidence: EvidenceReference,
    claim_scopes: tuple[EvidenceReference, ...],
) -> bool:
    """Allow uncited contradictions only for a proven identical entity scope."""
    if evidence.row_scope != "exact_entity" or not _has_entity_scope(evidence):
        return False
    return any(
        evidence.entity_table.casefold() == scope.entity_table.casefold()
        and evidence.identifier_column.casefold() == scope.identifier_column.casefold()
        and evidence.identifier_value == scope.identifier_value
        for scope in claim_scopes
    )


def _eligible_contradiction(
    evidence: EvidenceReference,
    claim_scopes: tuple[EvidenceReference, ...],
) -> bool:
    if claim_scopes:
        return _matches_any_claim_scope(evidence, claim_scopes)
    return True


def _unsupported_causal_explanation(
    statement: str,
    evidence: list[EvidenceReference],
) -> bool:
    match = re.search(r"\b(?:because|due to|caused by)\b(.+)$", statement, re.I)
    if not match:
        return False
    clause_tokens = {
        token
        for token in _normalized(match.group(1)).split()
        if len(token) >= 4 and token not in {"because", "required", "source", "value"}
    }
    evidence_text = _normalized(
        " ".join(
            f"{item.title} {item.supports_claim} {item.columns} {item.rows}"
            for item in evidence
        )
    )
    return bool(clause_tokens and not any(token in evidence_text for token in clause_tokens))


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _reference_supports_statement(statement: str, evidence: EvidenceReference) -> bool:
    normalized = _normalized(statement)
    if evidence.zero_row_result:
        if evidence.evidence_semantics != "verified_absence":
            return False
        absence_terms = (
            " no ",
            "not found",
            "none",
            "zero",
            "no matching",
            "absent",
            "missing",
        )
        return any(term in normalized for term in absence_terms)
    if not evidence.rows:
        return False
    for row in evidence.rows:
        for column, value in row.items():
            column_text = _normalized(column)
            if value is None:
                if column_text.replace(" ", "") in normalized.replace(" ", "") and any(
                    term in normalized for term in ("missing", "null", "not set", "absent")
                ):
                    return True
                continue
            value_text = _normalized(value)
            column_mentioned = column_text.replace(" ", "") in normalized.replace(" ", "")
            if (
                value_text
                and len(value_text) >= 2
                and value_text in normalized
                and (column_mentioned or len(value_text) >= 4)
            ):
                return True
    support_text = _normalized(f"{evidence.title} {evidence.supports_claim}")
    meaningful = [token for token in normalized.split() if len(token) >= 5]
    return bool(meaningful and sum(token in support_text for token in meaningful) >= 2)


def _reference_contradicts_statement(statement: str, evidence: EvidenceReference) -> bool:
    normalized = _normalized(statement)
    if not evidence.rows:
        return False
    for row in evidence.rows:
        for column, value in row.items():
            column_text = _normalized(column)
            column_key = column_text.replace(" ", "")
            compact = normalized.replace(" ", "")
            if not column_key or column_key not in compact or value is None:
                continue
            value_text = _normalized(value)
            if value_text and value_text not in normalized:
                column_pattern = r"\s*".join(map(re.escape, column_text.split()))
                assignment = re.search(
                    rf"{column_pattern}\s+(?:is\s+|has\s+)?([a-z0-9_-]+)",
                    normalized,
                )
                if assignment and _normalized(assignment.group(1)) != value_text:
                    return True
    return False
