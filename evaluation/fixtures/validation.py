from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from evaluation.framework.contracts import ScenarioContract

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
INTERNAL_PREFIX = re.compile(r"(?i)^(?:MSG|CORR|AUD|EX|ENTITY|SQL)-")


def manifest_sql_consistency(scenario: ScenarioContract) -> dict[str, Any]:
    value = scenario.expected_entity_value
    reasons: list[str] = []
    if not value:
        reasons.append("expected entity metadata is missing")
    question_value = scenario.expected_entity_question_value or value
    if question_value and question_value.casefold() not in scenario.question.casefold():
        reasons.append("question does not reference expected entity")
    if INTERNAL_PREFIX.match(value or ""):
        reasons.append("expected business entity uses a diagnostic/message prefix")
    scripts = {}
    for label, source in (
        ("setup", scenario.setup_script),
        ("verification", scenario.verification_script),
        ("cleanup", scenario.cleanup_script),
    ):
        path = Path(source)
        scripts[label] = path.read_text(encoding="utf-8") if path.is_file() else ""
        if not scripts[label]:
            reasons.append(f"{label} SQL is missing")
    if value and value.casefold() not in scripts["setup"].casefold():
        reasons.append("setup SQL does not reference expected entity")
    if value and value.casefold() not in scripts["verification"].casefold():
        if scenario.expected_entity_match_mode != "partial_ambiguous" or question_value.casefold() not in scripts["verification"].casefold():
            reasons.append("verification SQL does not reference expected entity")
    if value and value.casefold() not in scripts["cleanup"].casefold():
        partial = value.rsplit("-", 1)[0]
        if partial.casefold() not in scripts["cleanup"].casefold():
            reasons.append("cleanup SQL does not target expected entity or declared prefix")
    expected_object = f"{scenario.expected_entity_schema}.{scenario.expected_entity_table}".casefold()
    if scenario.expected_entity_table and not any(
        scenario.expected_entity_table.casefold() in scripts[name].casefold()
        for name in ("setup", "verification", "cleanup")
    ):
        reasons.append(f"fixture SQL does not reference entity object {expected_object}")
    if scenario.expected_defect_value and scenario.expected_defect_value.casefold() not in scripts["setup"].casefold():
        reasons.append("setup SQL does not reference expected defect linkage value")
    return {
        "status": "CONSISTENT" if not reasons else "FIXTURE_MANIFEST_MISMATCH",
        "consistent": not reasons,
        "reasons": reasons,
    }


def validate_identifiers(scenario: ScenarioContract) -> None:
    for name, value in (
        ("schema", scenario.expected_entity_schema),
        ("table", scenario.expected_entity_table),
        ("column", scenario.expected_entity_column),
        ("defect_table", scenario.expected_defect_table),
        ("defect_column", scenario.expected_defect_column),
        ("entity_link_column", scenario.expected_entity_link_column),
        ("defect_link_column", scenario.expected_defect_link_column),
    ):
        if value and not IDENTIFIER.fullmatch(value):
            raise ValueError(f"Invalid fixture {name} identifier: {value}")
