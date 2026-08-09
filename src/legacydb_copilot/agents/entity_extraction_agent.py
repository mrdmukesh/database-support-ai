from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExtractedEntity:
    entity_type: str
    value: str


@dataclass(frozen=True)
class StructuredBusinessIdentifier:
    field_name: str
    value: Any
    value_type: str
    source_text: str
    confidence: float
    schema_name: str = ""
    table_name: str = ""
    qualified_field_name: str = ""


@dataclass(frozen=True)
class EntityExtractionResult:
    entities: list[ExtractedEntity]
    suspected_issue: str | None
    likely_module: str | None
    application_name: str | None = None
    business_keywords: list[str] | None = None
    structured_identifiers: list[StructuredBusinessIdentifier] | None = None
    affected_attributes: list[str] | None = None
    symptoms: list[str] | None = None


_IDENTIFIER_FIELD_SUFFIX = re.compile(
    r"(?:id|number|code|key|ref|reference)$", re.IGNORECASE
)


def _typed_identifier_value(raw: str) -> tuple[Any, str]:
    value = raw.strip().strip("'\"")
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value), "integer"
    if re.fullmatch(r"[-+]?\d+\.\d+", value):
        return float(value), "number"
    return value, "string"


def extract_structured_identifiers(question: str) -> list[StructuredBusinessIdentifier]:
    """Extract explicit identifier-field/value pairs without interpreting their domain."""
    identifier = r"[A-Za-z_][A-Za-z0-9_$]*"
    identifier_field = (
        r"(?:[A-Za-z_][A-Za-z0-9_$]*?"
        r"(?:id|number|code|key|ref|reference)|[A-Za-z_][A-Za-z0-9_$]*\s+ID)"
    )
    qualified = rf"(?:{identifier}\.){{0,2}}{identifier_field}"
    value = r"(?:'[^']+'|\"[^\"]+\"|[A-Za-z0-9][A-Za-z0-9_.\-/]*)"
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_$])(?P<field>{qualified})\s*(?P<operator>=|:|\s)\s*(?P<value>{value})",
        re.IGNORECASE,
    )
    found: list[StructuredBusinessIdentifier] = []
    seen: set[tuple[str, str]] = set()
    for match in pattern.finditer(question):
        raw_field = re.sub(r"\s+ID$", "Id", match.group("field"), flags=re.IGNORECASE)
        parts = raw_field.split(".")
        field_name = parts[-1]
        if not _IDENTIFIER_FIELD_SUFFIX.search(field_name):
            continue
        if (
            len(parts) == 1
            and "_" not in field_name
            and " " not in match.group("field")
            and not re.search(r"[a-z][A-Z]", field_name)
            and not re.search(r"[A-Z].*[A-Z]", field_name)
        ):
            continue
        raw_value = match.group("value")
        if raw_value.casefold().strip("'\"") == "null":
            continue
        typed_value, value_type = _typed_identifier_value(raw_value)
        key = (raw_field.casefold(), str(typed_value).casefold())
        if key in seen:
            continue
        seen.add(key)
        schema_name = parts[-3] if len(parts) == 3 else ""
        table_name = parts[-2] if len(parts) >= 2 else ""
        found.append(
            StructuredBusinessIdentifier(
                field_name=field_name,
                schema_name=schema_name,
                table_name=table_name,
                qualified_field_name=raw_field if len(parts) >= 2 else "",
                value=typed_value,
                value_type=value_type,
                source_text=match.group(0),
                confidence=1.0 if len(parts) >= 2 or match.group("operator") in {"=", ":"} else 0.95,
            )
        )
    return found


def is_explicit_routine_identifier(value: str) -> bool:
    """Return whether a token has the shape of an explicitly named SQL routine."""
    return bool(
        "." in value
        or "_" in value
        or re.search(r"[a-z][A-Z]", value)
    )


def _unique(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for unique within entity_extraction_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in entity_extraction_agent.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    seen: set[tuple[str, str]] = set()
    result: list[ExtractedEntity] = []
    for entity in entities:
        key = (entity.entity_type, entity.value)
        if key not in seen:
            seen.add(key)
            result.append(entity)
    return result


_CONCEPT_STOP_WORDS = {
    "about",
    "access",
    "affected",
    "against",
    "analyze",
    "because",
    "below",
    "cause",
    "check",
    "created",
    "database",
    "explain",
    "failed",
    "find",
    "from",
    "generated",
    "issue",
    "missing",
    "null",
    "only",
    "problem",
    "question",
    "record",
    "records",
    "root",
    "show",
    "table",
    "tables",
    "where",
    "with",
    "without",
}


def _concept_tokens(question: str) -> list[str]:
    tokens: list[str] = []
    for token in re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]{1,}\b", question):
        lowered = token.lower()
        if lowered in _CONCEPT_STOP_WORDS:
            continue
        if token.upper() in {"SQL", "DB", "AI", "MVP", "RCA"}:
            continue
        tokens.append(token)
    return tokens


def _business_identifiers(question: str) -> list[str]:
    """Extract complete identifier candidates without interpreting their domain."""
    candidates: list[tuple[int, str]] = []
    separated = re.compile(
        r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+)+)(?![A-Za-z0-9])"
    )
    spaced = re.compile(
        r"(?<![A-Za-z0-9])([A-Z]{2,12}(?:\s+[A-Za-z0-9]+){1,4})(?![A-Za-z0-9])"
    )
    for pattern in (separated, spaced):
        for match in pattern.finditer(question):
            value = match.group(1)
            if any(character.isdigit() for character in value):
                candidates.append((match.start(1), value))
    return [value for _, value in sorted(set(candidates), key=lambda item: item[0])]


def extract_entities(question: str) -> EntityExtractionResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Extracts business keys, stored procedure names, status codes, modules, and searchable terms from a question.

    Input:
        Raw user question.

    Output:
        EntityExtractionResult used by metadata search, safe SQL planning, evidence focus, and RAG retrieval.

    Called by:
        Main /chat/ask orchestration immediately after intent detection.

    Flow:
        User question -> Intent Agent -> Entity Extraction -> Metadata Discovery -> Safe SQL Planner.

    Safety:
        Extraction is string analysis only. It must not assume domain-specific tables or execute SQL.
    """

    entities: list[ExtractedEntity] = []
    structured_identifiers = extract_structured_identifiers(question)
    for identifier in structured_identifiers:
        entities.append(ExtractedEntity("business_identifier", str(identifier.value)))
    application_name = None
    app_match = re.search(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*)\s+(System|Application|App|Database|DB)\b", question)
    if app_match:
        application_name = f"{app_match.group(1)} {app_match.group(2)}"
        entities.append(ExtractedEntity("application_name", application_name))
    business_key_pattern = r"\b(?:[A-Z]{1,8}\d{2,}[A-Z0-9]*|\d{2,}[A-Z]{1,8})\b"
    business_keys = set(_business_identifiers(question) + re.findall(business_key_pattern, question))
    for value in business_keys:
        entities.append(ExtractedEntity("exact_id_or_code", value))
        entities.append(ExtractedEntity("business_identifier", value))
    routine_identifier = (
        r"[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?"
    )
    routine_pattern = (
        rf"\b(?:stored(?:\s+|-)procedure|procedure|function|view|trigger)"
        rf"\s+(?:named\s+|called\s+)?({routine_identifier})\b"
    )
    routines = [
        value
        for value in re.findall(routine_pattern, question, re.I)
        if is_explicit_routine_identifier(value)
    ]
    routines.extend(
        ".".join(value)
        for value in re.findall(
            r"\[?([a-zA-Z_][a-zA-Z0-9_]*)\]?\.\[?((?:sp|usp|fn|tr)_[a-zA-Z0-9_]+)\]?",
            question,
            re.I,
        )
    )
    routines.extend(
        re.findall(r"(?<![.\w\[])(?:sp|usp|fn|tr)_[a-zA-Z0-9_]+\b", question, re.I)
    )
    for value in dict.fromkeys(routines):
        entities.append(ExtractedEntity("stored_procedure", value))
    for value in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b", question):
        entities.append(ExtractedEntity("possible_table", value[0]))
        entities.append(ExtractedEntity("possible_column", value[1]))
    for token in _concept_tokens(question):
        if token.isupper() and 2 <= len(token) <= 12:
            entities.append(ExtractedEntity("possible_column", token))
        else:
            entities.append(ExtractedEntity("possible_table_or_column", token))
    ignored_codes = {"SQL", "DB", "AI", "MVP"}
    for value in re.findall(r"\b[A-Z_]{3,}\b", question):
        if value in ignored_codes or (application_name and value in application_name.upper().split()):
            continue
        if any(value == business_key.split("-", 1)[0] for business_key in business_keys):
            continue
        if value not in {entity.value for entity in entities}:
            entities.append(ExtractedEntity("status_or_code", value))
    suspected_issue = None
    lowered = question.lower()
    for phrase in ("duplicate", "not generated", "not created", "query slow", "batch failed", "mismatch", "missing"):
        if phrase in lowered:
            suspected_issue = phrase
            break
    module = None
    generic_noise = {
        "are",
        "cause",
        "duplicate",
        "find",
        "group",
        "how",
        "investigate",
        "missing",
        "record",
        "records",
        "root",
        "show",
        "the",
        "where",
        "why",
        "with",
        "without",
    }
    for candidate in re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]{2,}\b", question):
        candidate = candidate.lower()
        if candidate not in generic_noise:
            module = candidate
            break
    business_keywords = [
        token.lower()
        for token in re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]{2,}\b", question)
        if token.upper() not in ignored_codes
    ][:20]
    return EntityExtractionResult(
        entities=_unique(entities),
        suspected_issue=suspected_issue,
        likely_module=module,
        application_name=application_name,
        business_keywords=business_keywords,
        structured_identifiers=structured_identifiers,
        affected_attributes=[
            entity.value
            for entity in _unique(entities)
            if entity.entity_type == "possible_table_or_column"
            and entity.value.casefold() not in {"why", "is", "the"}
            and not _IDENTIFIER_FIELD_SUFFIX.search(entity.value)
        ],
        symptoms=["NULL"] if re.search(r"\bNULL\b", question, re.IGNORECASE) else [],
    )
