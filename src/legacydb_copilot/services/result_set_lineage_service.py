from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any

from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    build_deterministic_root_cause_claim,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


class RowExclusionStatus(StrEnum):
    GENERATED = "GENERATED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class OutputTarget:
    symptom_type: str
    output_phrase: str
    source_text: str
    confidence: float
    qualifiers: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JoinLineage:
    join_type: str
    right_object: str
    right_alias: str
    on_predicate: str


@dataclass(frozen=True)
class ResultSetLineage:
    producer_object: str
    base_object: str
    base_alias: str
    joins: tuple[JoinLineage, ...]
    where_predicate: str
    having_predicate: str
    group_by: tuple[str, ...]
    output_aliases: tuple[str, ...]
    parameters: tuple[str, ...]
    anti_join_predicates: tuple[str, ...]
    from_clause: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutputProducerCandidate:
    producer_object: str
    score: float
    reasons: tuple[str, ...]
    lineage: ResultSetLineage
    selected: bool = False


@dataclass(frozen=True)
class RowExclusionCandidate:
    candidate_id: str
    candidate_type: str
    producer_object: str
    condition: str
    verification_query: str
    verification_parameters: dict[str, Any]
    status: RowExclusionStatus = RowExclusionStatus.GENERATED
    supporting_evidence_ids: tuple[str, ...] = ()
    reason: str = ""


_MISSING_OUTPUT = re.compile(
    r"\b(?:missing|absent|excluded|not\s+(?:showing|appearing|included|listed))\s+"
    r"(?:from|in)\s+(?:the\s+)?(?P<output>.+?)(?=\s+for\s+\d{4}\b|[?.!,]|$)",
    re.I,
)


def extract_output_target(question: str) -> OutputTarget | None:
    match = _MISSING_OUTPUT.search(question)
    if not match:
        return None
    phrase = " ".join(match.group("output").split()).strip()
    if not phrase:
        return None
    years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", question)]
    named_parameters = {
        name.casefold(): int(value)
        for name, value in re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|:)?\s*(-?\d+)\b",
            question,
        )
    }
    return OutputTarget(
        symptom_type="MISSING_FROM_OUTPUT",
        output_phrase=phrase,
        source_text=match.group(0),
        confidence=0.94,
        qualifiers={"years": years, "parameters": named_parameters},
    )


def _clean_identifier(value: str) -> str:
    return value.strip().strip('[]`"')


def _clause(definition: str, start: str, stops: str) -> str:
    match = re.search(rf"\b{start}\b\s+(.*?)(?=\b(?:{stops})\b|;|$)", definition, re.I | re.S)
    return " ".join(match.group(1).split()) if match else ""


def parse_result_set_lineage(producer_object: str, definition: str) -> ResultSetLineage | None:
    if not definition or not re.search(r"\bselect\b", definition, re.I):
        return None
    select_match = re.search(r"\bselect\b\s+(.*?)\s+\bfrom\b", definition, re.I | re.S)
    from_match = re.search(
        r"\bfrom\b\s+(.*?)(?=\bwhere\b|\bgroup\s+by\b|\bhaving\b|\border\s+by\b|;|$)",
        definition,
        re.I | re.S,
    )
    if not select_match or not from_match:
        return None
    from_clause = " ".join(from_match.group(1).split())
    base_match = re.match(
        r"(?P<object>[\[\]`\"A-Za-z0-9_.]+)(?:\s+(?:AS\s+)?(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?",
        from_clause,
        re.I,
    )
    if not base_match:
        return None
    base_object = _clean_identifier(base_match.group("object"))
    base_alias = base_match.group("alias") or base_object.split(".")[-1]
    joins: list[JoinLineage] = []
    join_pattern = re.compile(
        r"\b(?:(INNER|LEFT(?:\s+OUTER)?|RIGHT(?:\s+OUTER)?|FULL(?:\s+OUTER)?|CROSS)\s+)?JOIN\s+"
        r"([\[\]`\"A-Za-z0-9_.]+)(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?\s+ON\s+"
        r"(.*?)(?=\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b|$)",
        re.I | re.S,
    )
    for match in join_pattern.finditer(from_clause):
        joins.append(
            JoinLineage(
                join_type=" ".join((match.group(1) or "INNER").upper().split()),
                right_object=_clean_identifier(match.group(2)),
                right_alias=match.group(3) or _clean_identifier(match.group(2)).split(".")[-1],
                on_predicate=" ".join(match.group(4).split()),
            )
        )
    select_list = select_match.group(1)
    output_aliases = tuple(
        dict.fromkeys(
            _clean_identifier(value)
            for value in re.findall(
                r"(?:\bAS\s+|\s+)([\[\]`\"A-Za-z_][\[\]`\"A-Za-z0-9_]*)\s*(?:,|$)",
                select_list,
                re.I,
            )
        )
    )
    where = _clause(definition, "where", r"group\s+by|having|order\s+by")
    having = _clause(definition, "having", r"order\s+by")
    group_text = _clause(definition, r"group\s+by", r"having|order\s+by")
    anti_joins = tuple(
        " ".join(item.split())
        for item in re.findall(r"\bNOT\s+EXISTS\s*\((SELECT\s+.*?\))", definition, re.I | re.S)
    )
    return ResultSetLineage(
        producer_object=producer_object,
        base_object=base_object,
        base_alias=base_alias,
        joins=tuple(joins),
        where_predicate=where,
        having_predicate=having,
        group_by=tuple(part.strip() for part in group_text.split(",") if part.strip()),
        output_aliases=output_aliases,
        parameters=tuple(dict.fromkeys(re.findall(r"@[A-Za-z_][A-Za-z0-9_]*", definition))),
        anti_join_predicates=anti_joins,
        from_clause=from_clause,
    )


def _terms(value: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return {term.casefold() for term in re.findall(r"[A-Za-z0-9]+", expanded) if len(term) > 1}


def resolve_output_producers(
    target: OutputTarget,
    procedures: list[ProcedureAnalysis],
    *,
    entity_table: str = "",
    persisted_lineages: dict[str, dict[str, Any]] | None = None,
) -> list[OutputProducerCandidate]:
    target_terms = _terms(target.output_phrase)
    candidates: list[OutputProducerCandidate] = []
    persisted = {key.casefold(): value for key, value in (persisted_lineages or {}).items()}
    for procedure in procedures:
        raw = persisted.get(procedure.name.casefold())
        lineage = (
            ResultSetLineage(
                producer_object=raw["producer_object"],
                base_object=raw["base_object"],
                base_alias=raw["base_alias"],
                joins=tuple(JoinLineage(**item) for item in raw.get("joins", [])),
                where_predicate=raw.get("where_predicate", ""),
                having_predicate=raw.get("having_predicate", ""),
                group_by=tuple(raw.get("group_by", [])),
                output_aliases=tuple(raw.get("output_aliases", [])),
                parameters=tuple(raw.get("parameters", [])),
                anti_join_predicates=tuple(raw.get("anti_join_predicates", [])),
                from_clause=raw.get("from_clause", ""),
            )
            if raw
            else parse_result_set_lineage(procedure.name, procedure.definition)
        )
        if lineage is None:
            continue
        name_hits = target_terms & _terms(procedure.name)
        alias_hits = (
            target_terms & set().union(*(_terms(item) for item in lineage.output_aliases))
            if lineage.output_aliases
            else set()
        )
        reads_entity = bool(entity_table) and any(
            item.casefold().split(".")[-1] == entity_table.casefold().split(".")[-1]
            for item in (lineage.base_object, *(join.right_object for join in lineage.joins))
        )
        score = len(name_hits) * 25.0 + len(alias_hits) * 8.0 + (12.0 if reads_entity else 0.0)
        if score <= 0:
            continue
        reasons = (
            [f"Output-name terms matched: {', '.join(sorted(name_hits))}."] if name_hits else []
        )
        if reads_entity:
            reasons.append(f"SELECT-producing routine reads resolved entity table {entity_table}.")
        if alias_hits:
            reasons.append(f"Returned output aliases matched: {', '.join(sorted(alias_hits))}.")
        candidates.append(OutputProducerCandidate(procedure.name, score, tuple(reasons), lineage))
    candidates.sort(key=lambda item: (item.score, item.producer_object), reverse=True)
    return [replace(item, selected=index == 0) for index, item in enumerate(candidates)]


def _parameterize(
    predicate: str, lineage: ResultSetLineage, target: OutputTarget
) -> tuple[str, dict[str, Any]]:
    values: dict[str, Any] = {}
    result = predicate
    years = list(target.qualifiers.get("years") or [])
    supplied = {
        str(key).casefold(): value
        for key, value in (target.qualifiers.get("parameters") or {}).items()
    }
    for parameter in lineage.parameters:
        key = parameter[1:].casefold()
        value = supplied.get(key)
        if value is None and years and any(marker in key for marker in ("year", "date")):
            value = years[0]
        if value is not None:
            bind = f"output_{key}"
            result = re.sub(re.escape(parameter) + r"\b", f":{bind}", result, flags=re.I)
            values[bind] = value
    return result, values


def _entity_alias(lineage: ResultSetLineage, entity_table: str) -> str:
    leaf = entity_table.casefold().split(".")[-1]
    if lineage.base_object.casefold().split(".")[-1] == leaf:
        return lineage.base_alias
    match = next(
        (item for item in lineage.joins if item.right_object.casefold().split(".")[-1] == leaf),
        None,
    )
    return match.right_alias if match else lineage.base_alias


def plan_row_exclusion_verification(
    *,
    target: OutputTarget,
    producer: OutputProducerCandidate,
    entity_table: str,
    identifier_column: str,
    identifier_value: Any,
) -> tuple[list[RowExclusionCandidate], list[PlannedQuery]]:
    lineage = producer.lineage
    alias = _entity_alias(lineage, entity_table)
    entity_bind = "output_entity_identifier"
    predicate, predicate_parameters = _parameterize(lineage.where_predicate, lineage, target)
    filters = [f"{alias}.{identifier_column} = :{entity_bind}"]
    if predicate:
        filters.append(f"({predicate})")
    membership_sql = (
        f"SELECT TOP (1) {alias}.{identifier_column} AS output_identifier "
        f"FROM {lineage.from_clause} WHERE " + " AND ".join(filters)
    )
    if lineage.group_by:
        group_items = list(lineage.group_by)
        if not any(identifier_column.casefold() in item.casefold() for item in group_items):
            group_items.append(f"{alias}.{identifier_column}")
        membership_sql += " GROUP BY " + ", ".join(group_items)
    if lineage.having_predicate:
        having, having_parameters = _parameterize(lineage.having_predicate, lineage, target)
        membership_sql += f" HAVING {having}"
        predicate_parameters.update(having_parameters)
    parameters = {entity_bind: identifier_value, **predicate_parameters}
    queries = [
        PlannedQuery(
            purpose=f"Verify exact entity membership in output {producer.producer_object}",
            sql=membership_sql,
            execution_sql=membership_sql,
            parameters=parameters,
            evidence_semantics="verified_absence",
            exact_cardinality=True,
            entity_table=entity_table,
            identifier_column=identifier_column,
            identifier_value=identifier_value,
            row_scope="exact_output_membership",
        )
    ]
    candidates: list[RowExclusionCandidate] = []
    for join in lineage.joins:
        if join.join_type != "INNER":
            continue
        key_match = re.search(
            rf"\b{re.escape(join.right_alias)}\.([A-Za-z_][A-Za-z0-9_]*)", join.on_predicate, re.I
        )
        if not key_match:
            continue
        sql = (
            f"SELECT {alias}.{identifier_column}, CASE WHEN "
            f"{join.right_alias}.{key_match.group(1)} IS NULL THEN 1 ELSE 0 END "
            f"AS exclusion_condition_met FROM {lineage.base_object} "
            f"{lineage.base_alias} "
            f"LEFT JOIN {join.right_object} {join.right_alias} ON {join.on_predicate} "
            f"WHERE {alias}.{identifier_column} = :{entity_bind}"
        )
        candidate_id = f"ROW-CAUSE-{len(candidates) + 1}"
        candidates.append(
            RowExclusionCandidate(
                candidate_id,
                "INNER_JOIN_RELATED_ROW_ABSENCE",
                producer.producer_object,
                f"INNER JOIN requires a matching row in {join.right_object}",
                sql,
                {entity_bind: identifier_value},
                reason="A missing match on the mandatory side removes the entity row.",
            )
        )
        queries.append(
            PlannedQuery(
                purpose=f"Row exclusion verification {candidate_id}",
                sql=sql,
                execution_sql=sql,
                parameters={entity_bind: identifier_value},
                evidence_semantics="row_exclusion_verification",
                exact_cardinality=True,
                entity_table=entity_table,
                identifier_column=identifier_column,
                identifier_value=identifier_value,
                row_scope="exact_identifier_row_exclusion",
            )
        )
    if predicate:
        sql = (
            f"SELECT {alias}.{identifier_column}, CASE WHEN ({predicate}) THEN 0 ELSE 1 END "
            f"AS exclusion_condition_met FROM {lineage.base_object} {lineage.base_alias} "
            f"WHERE {alias}.{identifier_column} = :{entity_bind}"
        )
        candidate_id = f"ROW-CAUSE-{len(candidates) + 1}"
        candidates.append(
            RowExclusionCandidate(
                candidate_id,
                "WHERE_PREDICATE_REJECTION",
                producer.producer_object,
                predicate,
                sql,
                parameters,
                reason="The exact entity fails a producer WHERE predicate.",
            )
        )
        queries.append(
            PlannedQuery(
                purpose=f"Row exclusion verification {candidate_id}",
                sql=sql,
                execution_sql=sql,
                parameters=parameters,
                evidence_semantics="row_exclusion_verification",
                exact_cardinality=True,
                entity_table=entity_table,
                identifier_column=identifier_column,
                identifier_value=identifier_value,
                row_scope="exact_identifier_row_exclusion",
            )
        )
    if lineage.having_predicate:
        having, having_parameters = _parameterize(lineage.having_predicate, lineage, target)
        group_items = list(lineage.group_by)
        if not any(identifier_column.casefold() in item.casefold() for item in group_items):
            group_items.append(f"{alias}.{identifier_column}")
        sql = (
            f"SELECT {alias}.{identifier_column}, CASE WHEN ({having}) THEN 0 ELSE 1 END "
            f"AS exclusion_condition_met FROM {lineage.from_clause} "
            f"WHERE {alias}.{identifier_column} = :{entity_bind} GROUP BY " + ", ".join(group_items)
        )
        candidate_id = f"ROW-CAUSE-{len(candidates) + 1}"
        candidate_parameters = {entity_bind: identifier_value, **having_parameters}
        candidates.append(
            RowExclusionCandidate(
                candidate_id,
                "HAVING_PREDICATE_REJECTION",
                producer.producer_object,
                having,
                sql,
                candidate_parameters,
                reason="The exact entity's aggregate group fails a producer HAVING predicate.",
            )
        )
        queries.append(
            PlannedQuery(
                purpose=f"Row exclusion verification {candidate_id}",
                sql=sql,
                execution_sql=sql,
                parameters=candidate_parameters,
                evidence_semantics="row_exclusion_verification",
                exact_cardinality=True,
                entity_table=entity_table,
                identifier_column=identifier_column,
                identifier_value=identifier_value,
                row_scope="exact_identifier_row_exclusion",
            )
        )
    for anti in lineage.anti_join_predicates:
        anti_predicate, anti_parameters = _parameterize(anti, lineage, target)
        sql = (
            f"SELECT {alias}.{identifier_column}, CASE WHEN EXISTS "
            f"({anti_predicate}) THEN 1 ELSE 0 END "
            f"AS exclusion_condition_met FROM {lineage.base_object} {lineage.base_alias} "
            f"WHERE {alias}.{identifier_column} = :{entity_bind}"
        )
        candidate_id = f"ROW-CAUSE-{len(candidates) + 1}"
        candidate_parameters = {entity_bind: identifier_value, **anti_parameters}
        candidates.append(
            RowExclusionCandidate(
                candidate_id,
                "ANTI_JOIN_NOT_EXISTS",
                producer.producer_object,
                f"NOT EXISTS ({anti_predicate})",
                sql,
                candidate_parameters,
                reason="The producer anti-join excludes the exact entity.",
            )
        )
        queries.append(
            PlannedQuery(
                purpose=f"Row exclusion verification {candidate_id}",
                sql=sql,
                execution_sql=sql,
                parameters=candidate_parameters,
                evidence_semantics="row_exclusion_verification",
                exact_cardinality=True,
                entity_table=entity_table,
                identifier_column=identifier_column,
                identifier_value=identifier_value,
                row_scope="exact_identifier_row_exclusion",
            )
        )
    return candidates, queries


def evaluate_row_exclusion_candidates(
    candidates: list[RowExclusionCandidate],
    evidence: list[EvidenceResult],
    producer: OutputProducerCandidate,
) -> list[RowExclusionCandidate]:
    membership = next(
        (
            item
            for item in evidence
            if item.purpose
            == f"Verify exact entity membership in output {producer.producer_object}"
        ),
        None,
    )
    output_absent = bool(
        membership
        and not membership.error
        and membership.execution_status == "succeeded"
        and not membership.rows
    )
    evaluated: list[RowExclusionCandidate] = []
    for candidate in candidates:
        item = next((value for value in evidence if candidate.candidate_id in value.purpose), None)
        if not output_absent or item is None or item.error or not item.rows:
            evaluated.append(replace(candidate, status=RowExclusionStatus.INSUFFICIENT_EVIDENCE))
            continue
        matched = any(int(row.get("exclusion_condition_met") or 0) == 1 for row in item.rows)
        ids = tuple(value for value in (membership.evidence_id, item.evidence_id) if value)
        producer_evidence = next(
            (
                value.evidence_id
                for value in evidence
                if value.purpose == f"Inspect calculation logic in {producer.producer_object}"
                and value.rows
            ),
            "",
        )
        entity_evidence = next(
            (
                value.evidence_id
                for value in evidence
                if value.row_scope == "exact_identifier" and value.rows and not value.error
            ),
            "",
        )
        ids = tuple(
            dict.fromkeys(
                [
                    *([entity_evidence] if entity_evidence else []),
                    *ids,
                    *([producer_evidence] if producer_evidence else []),
                ]
            )
        )
        evaluated.append(
            replace(
                candidate,
                status=RowExclusionStatus.VERIFIED if matched else RowExclusionStatus.REJECTED,
                supporting_evidence_ids=ids if matched else (),
            )
        )
    return evaluated


def row_exclusion_reasoning(
    candidates: list[RowExclusionCandidate],
    producer: OutputProducerCandidate,
    evidence: list[EvidenceResult],
) -> ReasoningResult | None:
    verified = next(
        (item for item in candidates if item.status is RowExclusionStatus.VERIFIED), None
    )
    if verified is None:
        return None
    conclusion = (
        f"The exact entity is absent from output produced by {producer.producer_object} because "
        f"the verified row-exclusion condition is: {verified.condition}."
    )
    claim = build_deterministic_root_cause_claim(
        conclusion, list(verified.supporting_evidence_ids), evidence
    )
    return ReasoningResult(
        summary=conclusion,
        likely_root_causes=[claim] if claim else [],
        supporting_evidence=[
            f"Output producer: {producer.producer_object}",
            f"Exclusion type: {verified.candidate_type}",
            f"Evidence: {', '.join(verified.supporting_evidence_ids)}",
        ],
        missing_evidence=[],
        recommended_fix=[
            "Review the verified output inclusion rule with the business owner "
            "before changing query semantics or source data."
        ],
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=["Changing result-set inclusion semantics can affect every consumer of the output."],
        confirmed_facts=[conclusion],
        inferred_findings=[],
        hypotheses=[],
        response_type="confirmed_root_cause",
    )
