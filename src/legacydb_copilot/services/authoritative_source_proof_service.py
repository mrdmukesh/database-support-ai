from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    build_deterministic_root_cause_claim,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


class ExactCardinality(StrEnum):
    NOT_FOUND = "ENTITY_NOT_FOUND"
    RESOLVED = "ENTITY_RESOLVED"
    AMBIGUOUS = "AMBIGUOUS_ENTITY"
    FAILED = "QUERY_FAILED"


@dataclass(frozen=True)
class DependencyContract:
    source_table: str
    source_field: str
    derived_output: str
    source_required: bool
    null_behavior: str
    calculation_object: str = ""
    upstream_origin_requested: bool = False
    calculation_validation_requested: bool = False


@dataclass(frozen=True)
class ResolvedIdentifier:
    table: str
    column: str
    column_type: str
    value: Any
    canonical_key: str
    alternate_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthoritativeProof:
    cardinality: ExactCardinality
    evidence: EvidenceResult
    contract: DependencyContract
    identifier: ResolvedIdentifier
    deterministic_cause_confirmed: bool
    stop_reason: str = ""


def infer_dependency_contract(
    metadata: MetadataSearchResult,
    procedures: list[ProcedureAnalysis],
    question: str,
) -> DependencyContract | None:
    """Infer required-source NULL propagation from inspected routine metadata."""
    for procedure in procedures:
        definition = procedure.definition or ""
        match = re.search(
            r"(?is)case\s+when\s+(?:\w+\.)?([A-Za-z_][A-Za-z0-9_]*)\s+"
            r"is\s+null\s+then\s+null.*?end\s+as\s+([A-Za-z_][A-Za-z0-9_]*)",
            definition,
        )
        if not match:
            continue
        source_field, derived_output = match.groups()
        table = next(
            (
                item.name
                for item in metadata.tables
                if source_field.casefold() in {column.casefold() for column in item.columns}
            ),
            "",
        )
        if not table:
            continue
        request_clauses = _explicit_request_clauses(question)
        upstream_requested = any(
            re.search(r"\b(?:why|origin|became|history|changed)\b", clause)
            and re.search(r"\b(?:null|missing|empty|absent)\b", clause)
            for clause in request_clauses
        )
        calculation_requested = any(
            procedure.name.casefold() in clause
            or re.search(
                r"\b(?:validate|inspect|check|trace)\b.*\b(?:calculation|logic|routine|procedure)\b",
                clause,
            )
            for clause in request_clauses
        )
        return DependencyContract(
            source_table=table,
            source_field=source_field,
            derived_output=derived_output,
            source_required=True,
            null_behavior="calculation_unavailable",
            calculation_object=procedure.name,
            upstream_origin_requested=upstream_requested,
            calculation_validation_requested=calculation_requested,
        )
    return None


def _explicit_request_clauses(question: str) -> tuple[str, ...]:
    """Return direct request clauses, excluding negated and conditional guidance."""
    normalized = question.casefold()
    normalized = re.sub(
        r"(?is)\bif\b(?=[^.]*\b(?:populated|not\s+null|valid\s+value)\b)"
        r".*?(?=\s+\d+\.\s|$)",
        " ",
        normalized,
    )
    clauses = re.split(r"[.!?]+", normalized)
    return tuple(
        clause.strip()
        for clause in clauses
        if re.search(
            r"(?:^\s*why\b|\b(?:investigate|determine|explain|find|trace|inspect|check|validate)\b)",
            clause,
        )
        and not re.search(r"\b(?:do\s+not|don't|unless|without)\b", clause)
        and not re.match(r"\s*if\b", clause)
    )


def resolved_identifier_from_metadata(
    resolution: dict[str, Any],
    metadata: MetadataSearchResult,
    *,
    preferred_table: str = "",
) -> ResolvedIdentifier | None:
    selected = resolution
    if preferred_table:
        selected = next(
            (
                candidate
                for candidate in resolution.get("candidates") or []
                if str(candidate.get("table") or "").casefold()
                == preferred_table.casefold()
            ),
            resolution,
        )
    table_name = str(selected.get("table") or selected.get("resolved_table") or "")
    column_name = str(selected.get("column") or selected.get("resolved_column") or "")
    value = resolution.get("matched_value")
    table = next(
        (item for item in metadata.tables if item.name.casefold() == table_name.casefold()),
        None,
    )
    if table is None or column_name not in table.columns or value is None:
        return None
    alternates = tuple(
        item
        for item in table.columns
        if item != column_name
        and re.search(r"(?:number|code|key|reference|ref|id)$", item, re.I)
    )
    return ResolvedIdentifier(
        table=table.name,
        column=column_name,
        column_type=table.column_types.get(column_name, "unknown"),
        value=value,
        canonical_key=(table.primary_key or [column_name])[0],
        alternate_columns=alternates,
    )


def build_primary_proof_query(
    identifier: ResolvedIdentifier,
    contract: DependencyContract,
) -> PlannedQuery:
    if identifier.table.casefold() != contract.source_table.casefold():
        raise ValueError("Resolved identifier and dependency source table do not match")
    columns = list(
        dict.fromkeys(
            [identifier.canonical_key, identifier.column, contract.source_field]
        )
    )
    return PlannedQuery(
        purpose=f"Prove one resolved entity and authoritative source in {identifier.table}",
        sql=(
            f"SELECT {', '.join(columns)} FROM {identifier.table} "
            f"WHERE {identifier.column} = :resolved_identifier"
        ),
        execution_sql=(
            f"SELECT {', '.join(columns)} FROM {identifier.table} "
            f"WHERE {identifier.column} = :resolved_identifier"
        ),
        parameters={"resolved_identifier": identifier.value},
        evidence_semantics="authoritative_source_proof",
        column_types={
            identifier.canonical_key: "unknown",
            identifier.column: identifier.column_type,
            contract.source_field: "unknown",
        },
        nullable_columns=(contract.source_field,),
        exact_cardinality=True,
    )


def classify_authoritative_proof(
    evidence: EvidenceResult,
    identifier: ResolvedIdentifier,
    contract: DependencyContract,
) -> AuthoritativeProof:
    if evidence.execution_status != "succeeded" or evidence.error:
        cardinality = ExactCardinality.FAILED
    elif evidence.row_count == 0:
        cardinality = ExactCardinality.NOT_FOUND
    elif evidence.row_count == 1:
        cardinality = ExactCardinality.RESOLVED
    else:
        cardinality = ExactCardinality.AMBIGUOUS
    row = evidence.rows[0] if cardinality is ExactCardinality.RESOLVED else {}
    explicit_null = contract.source_field in row and row[contract.source_field] is None
    confirmed = bool(contract.source_required and explicit_null)
    return AuthoritativeProof(
        cardinality=cardinality,
        evidence=evidence,
        contract=contract,
        identifier=identifier,
        deterministic_cause_confirmed=confirmed,
        stop_reason=(
            "DETERMINISTIC_REQUIRED_SOURCE_NULL_CONFIRMED" if confirmed else ""
        ),
    )


def should_stop_after_proof(proof: AuthoritativeProof | None) -> bool:
    return bool(
        proof
        and proof.deterministic_cause_confirmed
        and not proof.contract.upstream_origin_requested
        and not proof.contract.calculation_validation_requested
    )


def reasoning_from_authoritative_proof(proof: AuthoritativeProof) -> ReasoningResult:
    if not proof.deterministic_cause_confirmed:
        raise ValueError("A deterministic cause requires a confirmed authoritative proof")
    contract = proof.contract
    conclusion = (
        f"{contract.derived_output} is unavailable because its required authoritative "
        f"source {contract.source_field} is explicitly NULL."
    )
    claim = build_deterministic_root_cause_claim(
        conclusion,
        [proof.evidence.evidence_id],
        [proof.evidence],
    )
    return ReasoningResult(
        summary=conclusion,
        likely_root_causes=[claim] if claim else [],
        supporting_evidence=[proof.evidence.supports_claim],
        missing_evidence=[
            f"The evidence does not establish why {contract.source_field} became NULL."
        ],
        recommended_fix=[
            f"Verify the correct {contract.source_field} from the approved authoritative "
            f"source, enter it through the approved maintenance process, and rerun "
            f"the {contract.derived_output} calculation."
        ],
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=["Do not infer or directly overwrite an unverified source value."],
        confirmed_facts=[conclusion],
        inferred_findings=[],
        hypotheses=[],
        response_type="confirmed_root_cause",
    )
