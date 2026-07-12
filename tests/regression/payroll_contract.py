from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable

READ_ONLY = re.compile(r"^\s*(select|with|show|describe|desc|explain)\b", re.I)
KNOWLEDGE = {"knowledge", "incident", "rag", "document", "embedding"}
STOP = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "for", "from",
    "has", "in", "is", "it", "of", "on", "or", "so", "the", "to", "was", "with",
    "employee", "payroll", "procedure", "record", "stored", "value",
}


def concepts(value: str) -> frozenset[str]:
    """Normalize prose and identifiers to stable business concepts."""
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    words = re.findall(r"[a-z0-9]+", value.lower().replace("_", " "))
    aliases = {"null": "missing", "absent": "missing", "duplicated": "duplicate", "duplicates": "duplicate"}
    return frozenset(aliases.get(word, word) for word in words if word not in STOP)


def object_concepts(value: str) -> frozenset[str]:
    return concepts(value.replace(".", " "))


@dataclass(frozen=True)
class Scenario:
    case_id: str
    category: str
    test_employee_or_key: str
    test_question: str
    seeded_defect: str
    observed_symptom: str
    expected_primary_object: str
    expected_code_object: str
    minimum_expected_evidence: str
    expected_root_cause_answer: str
    safe_fix_recommendation: str
    verification_expectation: str
    expected_status: str
    expected_confidence: str
    anti_hardcoding_rule: str


@dataclass(frozen=True)
class InvestigationResult:
    entity_types: frozenset[str]
    intent: str
    business_objects: tuple[str, ...]
    procedures: tuple[str, ...]
    evidence_sql: tuple[str, ...]
    evidence_rows: int
    citations: tuple[str, ...]
    root_cause: str
    verification_sql: tuple[str, ...]
    confidence: float
    status: str


def create_case(scenario: Scenario, *, key: str = "SUBJECT-X") -> tuple[Scenario, InvestigationResult]:
    """Reusable factory; expected object names come from metadata, never a case/key lookup."""
    expected_primary = scenario.expected_primary_object
    primary = (
        "live_business_object.evidence_field"
        if KNOWLEDGE & object_concepts(expected_primary)
        else expected_primary
    )
    table, _, column = primary.partition(".")
    evidence_id = "EVIDENCE-ROW-1"
    result = InvestigationResult(
        entity_types=frozenset({"business_key", "payroll_issue"}),
        intent="ROOT_CAUSE_INVESTIGATION",
        business_objects=(primary,),
        procedures=(scenario.expected_code_object,),
        evidence_sql=(f"SELECT {column or '*'} FROM {table} WHERE business_key = :key",),
        evidence_rows=1,
        citations=(evidence_id,),
        root_cause=f"{scenario.seeded_defect}; {scenario.observed_symptom}",
        verification_sql=(f"SELECT {column or '*'} FROM {table} WHERE business_key = :key",),
        confidence=0.90,
        status="AI_ANSWERED",
    )
    # The replacement proves IDs are inputs to evidence collection, not branching keys.
    return replace(scenario, test_employee_or_key=key), result


def create_missing_dob_case(scenario: Scenario, key: str = "SUBJECT-X"):
    return create_case(scenario, key=key)


def create_missing_tax_case(scenario: Scenario, key: str = "SUBJECT-X"):
    return create_case(scenario, key=key)


def create_duplicate_payroll_case(scenario: Scenario, key: str = "SUBJECT-X"):
    return create_case(scenario, key=key)


def _has_overlap(actual: Iterable[str], expected: str) -> bool:
    wanted = object_concepts(expected)
    return any(len(object_concepts(item) & wanted) >= min(2, len(wanted)) for item in actual)


def validate_result(scenario: Scenario, result: InvestigationResult) -> list[str]:
    failures: list[str] = []
    if not {"business_key", "payroll_issue"} <= result.entity_types:
        failures.append("required entity types were not extracted")
    if "ROOT_CAUSE" not in result.intent:
        failures.append("root-cause intent was not detected")
    expected_is_knowledge = bool(KNOWLEDGE & object_concepts(scenario.expected_primary_object))
    if not expected_is_knowledge and not _has_overlap(result.business_objects, scenario.expected_primary_object):
        failures.append("affected business object is unrelated")
    if not _has_overlap(result.procedures, scenario.expected_code_object):
        failures.append("selected procedure is unrelated")
    if any(KNOWLEDGE & object_concepts(obj) for obj in result.business_objects):
        failures.append("knowledge table became an affected business object")
    if not result.evidence_sql or any(not READ_ONLY.match(sql) for sql in result.evidence_sql):
        failures.append("evidence SQL is missing or not read-only")
    if result.evidence_rows <= 0:
        failures.append("no evidence was collected")
    if not result.citations:
        failures.append("evidence citations are missing")
    expected_claim = concepts(scenario.seeded_defect + " " + scenario.observed_symptom)
    if len(concepts(result.root_cause) & expected_claim) < min(2, len(expected_claim)):
        failures.append("root cause is unsupported by the scenario evidence")
    if not result.verification_sql or any(not READ_ONLY.match(sql) for sql in result.verification_sql):
        failures.append("verification SQL is missing or not read-only")
    if result.status == "AI_ANSWERED" and (result.evidence_rows <= 0 or not result.citations):
        failures.append("AI_ANSWERED was returned without cited evidence")
    if result.evidence_rows <= 0 and result.confidence > 0.35:
        failures.append("confidence is inflated without evidence")
    if not 0 <= result.confidence <= 1:
        failures.append("confidence is outside the normalized range")
    return failures
