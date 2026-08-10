from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    build_deterministic_root_cause_claim,
)
from legacydb_copilot.services.attribute_lineage_service import AttributeLineageCandidate
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


class CausalVerificationStatus(StrEnum):
    GENERATED = "GENERATED"
    SUPPORTED = "SUPPORTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class CausalCandidate:
    candidate_id: str
    producer_object: str
    affected_attribute: str
    source_expression: str
    source_columns: tuple[str, ...]
    candidate_condition: str
    expected_output: str
    entity_identifier: dict[str, Any]
    verification_query: str
    verification_parameters: dict[str, Any]
    status: CausalVerificationStatus = CausalVerificationStatus.GENERATED
    supporting_evidence_ids: tuple[str, ...] = ()
    rejecting_evidence_ids: tuple[str, ...] = ()
    reason: str = ""

    def to_trace(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


def _clean_condition(condition: str) -> str:
    value = re.sub(r"\[([^]]+)\]", r"\1", condition.strip())
    value = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\.", "", value)
    return " ".join(value.split())


def _safe_condition(condition: str, columns: tuple[str, ...]) -> bool:
    if not condition or ";" in condition or re.search(
        r"\b(insert|update|delete|drop|alter|exec|execute|merge)\b", condition, re.I
    ):
        return False
    identifiers = {
        token.casefold()
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", condition)
    }
    allowed = {
        "is", "not", "null", "and", "or", "like", "in", "between", "true", "false",
        "coalesce", "isnull", "nullif", "cast", "convert", "case", "when", "then", "else", "end",
    } | {column.casefold() for column in columns}
    return identifiers <= allowed


def _conditions_for(
    lineage: AttributeLineageCandidate,
    procedure: ProcedureAnalysis | None,
    observed_null: bool,
) -> list[tuple[str, str, str]]:
    expression = lineage.expression
    candidates: list[tuple[str, str, str]] = []
    for match in re.finditer(
        r"\bwhen\s+(.*?)\s+then\s+(.*?)(?=\bwhen\b|\belse\b|\bend\b)",
        expression,
        re.I | re.S,
    ):
        condition = _clean_condition(match.group(1))
        output = " ".join(match.group(2).split())
        if observed_null and output.casefold() == "null":
            candidates.append((condition, "NULL", "CASE branch returns observed NULL"))
        elif not observed_null:
            candidates.append((condition, output, "CASE branch can produce affected output"))
    nullif = re.search(r"\bnullif\s*\(\s*([^,]+),\s*([^)]+)\)", expression, re.I)
    if observed_null and nullif:
        candidates.append(
            (_clean_condition(f"{nullif.group(1)} = {nullif.group(2)}"), "NULL", "NULLIF arguments compare equal")
        )
    if observed_null and re.search(r"\b(?:coalesce|isnull)\s*\(", expression, re.I):
        condition = " AND ".join(f"{column} IS NULL" for column in lineage.source_columns)
        if condition:
            candidates.append((condition, "NULL", "Fallback expression inputs are all NULL"))
    if observed_null and lineage.source_columns and not candidates:
        condition = " OR ".join(f"{column} IS NULL" for column in lineage.source_columns)
        candidates.append((condition, "NULL", "SQL expression propagates a NULL source input"))
    if procedure is not None:
        for match in re.finditer(r"\bif\s+(.+?)(?:\bbegin\b|\bselect\b)", procedure.definition, re.I | re.S):
            condition = _clean_condition(match.group(1))
            if condition and any(column.casefold() in condition.casefold() for column in lineage.source_columns):
                candidates.append((condition, "NULL" if observed_null else "BRANCH_OUTPUT", "IF branch controls producer output"))
    return list(dict.fromkeys(candidates))


def generate_causal_candidates(
    *,
    entities: EntityExtractionResult,
    lineage: list[AttributeLineageCandidate],
    procedures: list[ProcedureAnalysis],
) -> tuple[list[CausalCandidate], list[PlannedQuery]]:
    selected = next((item for item in lineage if item.selected), None)
    identifier = next(iter(entities.structured_identifiers or []), None)
    if selected is None or identifier is None:
        return [], []
    procedure = next(
        (item for item in procedures if item.name.casefold() == selected.producer.casefold()),
        None,
    )
    observed_null = any(item.casefold() == "null" for item in (entities.symptoms or []))
    generated: list[CausalCandidate] = []
    queries: list[PlannedQuery] = []
    for index, (condition, expected, reason) in enumerate(
        _conditions_for(selected, procedure, observed_null), start=1
    ):
        candidate_id = f"CAUSE-{index}"
        if not _safe_condition(condition, selected.source_columns):
            generated.append(
                CausalCandidate(
                    candidate_id, selected.producer, selected.attribute,
                    selected.expression, selected.source_columns, condition, expected,
                    {"field": identifier.field_name, "value": identifier.value}, "", {},
                    CausalVerificationStatus.INSUFFICIENT_EVIDENCE,
                    reason="Condition could not be represented by the safe SQL subset.",
                )
            )
            continue
        parameter = f"causal_entity_value_{index}"
        selected_columns = list(
            dict.fromkeys([selected.identifier_column, *selected.source_columns])
        )
        sql = (
            f"SELECT {', '.join(selected_columns)}, "
            f"CASE WHEN {condition} THEN 1 ELSE 0 END AS causal_condition_met "
            f"FROM {selected.target_table} WHERE {selected.identifier_column} = :{parameter}"
        )
        candidate = CausalCandidate(
            candidate_id, selected.producer, selected.attribute,
            selected.expression, selected.source_columns, condition, expected,
            {"field": identifier.field_name, "value": identifier.value},
            sql, {parameter: identifier.value}, reason=reason,
        )
        generated.append(candidate)
        queries.append(
            PlannedQuery(
                purpose=f"Causal verification {candidate_id} for {selected.attribute}",
                sql=sql,
                execution_sql=sql,
                parameters={parameter: identifier.value},
                evidence_semantics="causal_verification",
                exact_cardinality=True,
                entity_table=selected.target_table,
                identifier_column=selected.identifier_column,
                identifier_value=identifier.value,
                row_scope="exact_identifier_causal_verification",
            )
        )
    return generated, queries


def evaluate_causal_candidates(
    candidates: list[CausalCandidate], evidence: list[EvidenceResult]
) -> list[CausalCandidate]:
    evaluated: list[CausalCandidate] = []
    for candidate in candidates:
        if candidate.status is CausalVerificationStatus.INSUFFICIENT_EVIDENCE:
            evaluated.append(candidate)
            continue
        item = next(
            (value for value in evidence if candidate.candidate_id in value.purpose),
            None,
        )
        if item is None or item.error or item.execution_status != "succeeded" or not item.rows:
            evaluated.append(
                replace(candidate, status=CausalVerificationStatus.INSUFFICIENT_EVIDENCE)
            )
            continue
        matched = any(int(row.get("causal_condition_met") or 0) == 1 for row in item.rows)
        producer_evidence = next(
            (
                value.evidence_id for value in evidence
                if value.purpose == f"Inspect calculation logic in {candidate.producer_object}"
                and value.rows
            ),
            "",
        )
        supporting_ids = tuple(
            value for value in (item.evidence_id, producer_evidence) if value
        )
        evaluated.append(
            replace(
                candidate,
                status=(
                    CausalVerificationStatus.VERIFIED
                    if matched else CausalVerificationStatus.REJECTED
                ),
                supporting_evidence_ids=supporting_ids if matched else (),
                rejecting_evidence_ids=() if matched else (item.evidence_id,),
                reason=(
                    candidate.reason + "; exact entity values satisfy the producer condition."
                    if matched else candidate.reason + "; exact entity values reject the condition."
                ),
            )
        )
    return evaluated


def causal_reasoning(
    candidates: list[CausalCandidate], evidence: list[EvidenceResult]
) -> ReasoningResult | None:
    verified = next(
        (item for item in candidates if item.status is CausalVerificationStatus.VERIFIED),
        None,
    )
    if verified is None:
        return None
    conclusion = (
        f"For the exact entity {verified.entity_identifier['field']} = "
        f"{verified.entity_identifier['value']}, producer {verified.producer_object} "
        f"evaluates condition ({verified.candidate_condition}) and produces "
        f"{verified.affected_attribute} = {verified.expected_output}."
    )
    claim = build_deterministic_root_cause_claim(
        conclusion,
        list(verified.supporting_evidence_ids),
        evidence,
    )
    return ReasoningResult(
        summary=conclusion,
        likely_root_causes=[claim] if claim is not None else [],
        supporting_evidence=[
            f"Producer expression: {verified.source_expression}",
            f"Exact verification condition: {verified.candidate_condition}",
            f"Evidence: {', '.join(verified.supporting_evidence_ids)}",
        ],
        missing_evidence=[],
        recommended_fix=[
            "Correct the verified source condition through the authorized business-data path; "
            "do not mutate production data from this investigation."
        ],
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=["Changing producer semantics may affect all entities using the same calculation."],
        confirmed_facts=[conclusion],
        inferred_findings=[],
        hypotheses=[],
        response_type="confirmed_root_cause",
    )
