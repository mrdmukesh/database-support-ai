from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


@dataclass(frozen=True)
class AttributeLineageCandidate:
    attribute: str
    producer: str
    producer_type: str
    target_table: str
    identifier_column: str
    source_columns: tuple[str, ...]
    expression: str
    evidence_kind: str
    score: float
    selected: bool = False
    rejection_reason: str = ""

    def to_trace(self) -> dict[str, Any]:
        return asdict(self)


def _canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold().strip("[]`\""))


def _split_expressions(select_list: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(select_list):
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
        elif character == "," and depth == 0:
            result.append(select_list[start:index].strip())
            start = index + 1
    result.append(select_list[start:].strip())
    return [item for item in result if item]


def _output_expression(definition: str, attribute: str) -> str:
    wanted = _canonical(attribute)
    for select_list in re.findall(r"\bselect\s+(.*?)\s+\bfrom\b", definition, re.I | re.S):
        for expression in _split_expressions(select_list):
            alias_match = re.search(
                r"(?:\bas\s+|\s+)(\[?[A-Za-z_][A-Za-z0-9_]*\]?)\s*$",
                expression,
                re.I,
            )
            if alias_match and _canonical(alias_match.group(1)) == wanted:
                return expression[: alias_match.start()].strip()
            if _canonical(expression) == wanted:
                return expression
    return ""


def _source_columns(expression: str, columns: list[str]) -> tuple[str, ...]:
    tokens = {
        _canonical(match.group(0))
        for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", expression)
    }
    return tuple(column for column in columns if _canonical(column) in tokens)


def resolve_attribute_lineage(
    *,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
    procedures: list[ProcedureAnalysis],
    resolved_entities: list[dict[str, Any]],
) -> tuple[list[AttributeLineageCandidate], list[PlannedQuery]]:
    """Resolve stored or derived attributes using catalog objects and routine definitions."""
    attributes = [
        value for value in (entities.affected_attributes or [])
        if value.casefold() not in {"for", "from", "with", "without"}
    ]
    resolution = next(
        (
            item for item in resolved_entities
            if item.get("resolved_table") and item.get("resolved_column")
            and item.get("identifier_value", item.get("matched_value")) is not None
        ),
        None,
    )
    if not attributes or resolution is None:
        return [], []
    table_name = str(resolution["resolved_table"])
    identifier_column = str(resolution["resolved_column"])
    identifier_value = resolution.get("identifier_value", resolution.get("matched_value"))
    table = next(
        (item for item in metadata.tables if item.name.casefold() == table_name.casefold()),
        None,
    )
    if table is None:
        return [], []

    candidates: list[AttributeLineageCandidate] = []
    for attribute in attributes:
        stored = next(
            (column for column in table.columns if _canonical(column) == _canonical(attribute)),
            None,
        )
        if stored:
            candidates.append(
                AttributeLineageCandidate(
                    attribute, table.name, "STORED_COLUMN", table.name,
                    identifier_column, (stored,), stored, "direct_catalog_column", 100.0,
                )
            )
        for procedure in procedures:
            if not procedure.definition_available:
                continue
            reads_target = any(
                _canonical(name.split(".")[-1]) == _canonical(table.name.split(".")[-1])
                for name in procedure.tables_read
            )
            if not reads_target:
                continue
            expression = _output_expression(procedure.definition, attribute)
            if not expression:
                continue
            sources = _source_columns(expression, table.columns)
            candidates.append(
                AttributeLineageCandidate(
                    attribute, procedure.name, procedure.object_type, table.name,
                    identifier_column, sources, expression,
                    "definition_output_expression", 90.0 + len(sources),
                )
            )

    candidates.sort(key=lambda item: item.score, reverse=True)
    if not candidates:
        return [], []
    selected = candidates[0]
    candidates = [
        AttributeLineageCandidate(
            **{
                **asdict(item),
                "selected": item == selected,
                "rejection_reason": (
                    "Lower code-level attribute dependency score."
                    if item != selected else ""
                ),
            }
        )
        for item in candidates
    ]
    verification_columns = list(
        dict.fromkeys([identifier_column, *selected.source_columns])
    )
    if len(verification_columns) == 1 and selected.producer_type != "STORED_COLUMN":
        return candidates, []
    parameter = "attribute_entity_value"
    sql = (
        f"SELECT {', '.join(verification_columns)} FROM {table.name} "
        f"WHERE {identifier_column} = :{parameter}"
    )
    query = PlannedQuery(
        purpose=(
            f"Verify attribute lineage inputs for {selected.attribute} via "
            f"{selected.producer}"
        ),
        sql=sql,
        execution_sql=sql,
        parameters={parameter: identifier_value},
        evidence_semantics="attribute_lineage",
        exact_cardinality=True,
        entity_table=table.name,
        identifier_column=identifier_column,
        identifier_value=identifier_value,
        row_scope="exact_identifier_attribute_lineage",
    )
    return candidates, [query]
