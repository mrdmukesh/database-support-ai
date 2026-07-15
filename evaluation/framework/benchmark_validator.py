from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from evaluation.framework.contracts import ScenarioContract

DOMAINS = ("banking", "orders", "shipping", "payroll", "clinic")
DIFFICULTIES = {"easy": 20, "medium": 40, "hard": 30, "expert": 10}
REQUIRED_CATEGORIES = (
    "exact_entity_lookup", "partial_entity_resolution", "ambiguous_entity_resolution",
    "missing_downstream_record", "duplicate_transaction", "workflow_interruption",
    "exception_handling", "integration_failure", "queue_backlog", "retry_failure",
    "audit_history_inconsistency", "missing_reference_data", "stored_procedure_defect",
    "trigger_failure", "batch_processing_failure", "concurrency_race_condition",
    "transaction_rollback", "idempotency_issue", "incorrect_business_status",
    "multi_table_investigation",
)
FORBIDDEN_SQL = re.compile(r"\b(drop|truncate|alter|create\s+(?:login|user)|grant|revoke)\b", re.I)
EXPECTED_ANSWER_MARKERS = ("expected_root_cause", "acceptable_fix", "unsafe_recommendation")


@dataclass(frozen=True)
class BenchmarkIssue:
    code: str
    message: str
    scenario_id: str = ""


def validate_benchmark(
    scenarios: list[ScenarioContract], root: str | Path = ".", *, enforce_distribution: bool = True
) -> list[BenchmarkIssue]:
    base = Path(root)
    issues: list[BenchmarkIssue] = []
    ids = Counter(item.scenario_id for item in scenarios)
    for scenario_id, count in ids.items():
        if count > 1:
            issues.append(BenchmarkIssue("duplicate_id", f"scenario ID occurs {count} times", scenario_id))
    questions = Counter(_normalized(item.question) for item in scenarios)
    for item in scenarios:
        issues.extend(_validate_scenario(item, base))
        if questions[_normalized(item.question)] > 1:
            issues.append(BenchmarkIssue("duplicate_question", "investigation question is duplicated", item.scenario_id))
    if enforce_distribution:
        issues.extend(_validate_distribution(scenarios))
    return issues


def _validate_scenario(item: ScenarioContract, base: Path) -> list[BenchmarkIssue]:
    issues: list[BenchmarkIssue] = []
    required_collections = {
        "expected entities": item.expected_entities,
        "database objects": item.expected_database_objects,
        "relationships": item.expected_relationships,
        "required evidence": item.required_evidence,
        "remediation concepts": item.acceptable_fix_concepts,
        "unsafe recommendations": item.unsafe_recommendations,
        "citations": item.expected_citations,
        "tags": item.tags,
    }
    extended = "-benchmark-" in item.scenario_id
    if extended and not item.business_description.strip():
        issues.append(BenchmarkIssue("incomplete", "business description is missing", item.scenario_id))
    for label, values in required_collections.items():
        if extended and not values:
            issues.append(BenchmarkIssue("incomplete", f"{label} are missing", item.scenario_id))
    for script_name in (item.baseline_script, item.setup_script, item.verification_script, item.cleanup_script):
        path = base / script_name
        if not path.is_file():
            issues.append(BenchmarkIssue("missing_script", script_name, item.scenario_id))
            continue
        sql = path.read_text(encoding="utf-8")
        if FORBIDDEN_SQL.search(sql):
            issues.append(BenchmarkIssue("unsafe_sql", script_name, item.scenario_id))
    return issues


def _validate_distribution(scenarios: list[ScenarioContract]) -> list[BenchmarkIssue]:
    issues: list[BenchmarkIssue] = []
    domain_counts = Counter(item.domain for item in scenarios)
    difficulty_counts = Counter(item.difficulty for item in scenarios)
    for domain in DOMAINS:
        domain_items = [item for item in scenarios if item.domain == domain]
        if domain_counts[domain] != 25:
            issues.append(BenchmarkIssue("distribution", f"{domain} has {domain_counts[domain]} scenarios; expected 25"))
        new_categories = Counter(item.category for item in domain_items if "-benchmark-" in item.scenario_id)
        for category in REQUIRED_CATEGORIES:
            if new_categories[category] != 1:
                issues.append(BenchmarkIssue("category_coverage", f"{domain}/{category} count is {new_categories[category]}"))
    expected_total = {"easy": 20, "medium": 40, "hard": 30, "expert": 10}
    new_items = [item for item in scenarios if "-benchmark-" in item.scenario_id]
    actual = Counter(item.difficulty for item in new_items)
    for level, count in expected_total.items():
        if actual[level] != count:
            issues.append(BenchmarkIssue("difficulty_distribution", f"{level} has {actual[level]}; expected {count}"))
    return issues


def scan_production_answer_leakage(root: str | Path) -> list[BenchmarkIssue]:
    source = Path(root) / "src"
    issues: list[BenchmarkIssue] = []
    if not source.exists():
        return issues
    for path in source.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "evaluation_scenarios" in text or any(marker in text for marker in EXPECTED_ANSWER_MARKERS):
            issues.append(BenchmarkIssue("expected_answer_leakage", str(path)))
    return issues


def _normalized(value: str) -> str:
    return " ".join(value.lower().split())
