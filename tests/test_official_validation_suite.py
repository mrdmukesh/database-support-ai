from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evaluation" / "validation-suites" / "official-validation-25.json"


def _selected_scenarios() -> list[dict]:
    manifest = json.loads(SUITE.read_text(encoding="utf-8"))
    return [
        json.loads(
            next((ROOT / "evaluation_scenarios").glob(f"*/{scenario_id}/scenario.json")).read_text(
                encoding="utf-8"
            )
        )
        for scenario_id in manifest["scenarios"]
    ]


def test_official_validation_suite_is_balanced_and_unique() -> None:
    manifest = json.loads(SUITE.read_text(encoding="utf-8"))
    scenarios = _selected_scenarios()

    assert len(manifest["scenarios"]) == len(set(manifest["scenarios"])) == 25
    assert Counter(item["domain"] for item in scenarios) == {
        "banking": 5,
        "orders": 5,
        "shipping": 5,
        "clinic": 5,
        "payroll": 5,
    }
    assert {item["difficulty"] for item in scenarios} == {"easy", "medium", "hard", "expert"}
    assert {"duplicate_transaction", "retry_failure", "audit_history_inconsistency", "exception_handling"} <= {
        item["category"] for item in scenarios
    }


def test_official_validation_suite_contains_release_risk_cases() -> None:
    selected = set(json.loads(SUITE.read_text(encoding="utf-8"))["scenarios"])

    assert {
        "banking-benchmark-002",
        "shipping-benchmark-004",
        "shipping-benchmark-005",
        "shipping-benchmark-008",
        "orders-benchmark-010",
        "clinic-benchmark-017",
    } <= selected


def test_shipping_duplicate_fixture_proves_two_correlated_messages() -> None:
    fixture = ROOT / "evaluation_scenarios" / "shipping" / "shipping-benchmark-005"
    injection = (fixture / "inject.sql").read_text(encoding="utf-8")
    verification = (fixture / "verify.sql").read_text(encoding="utf-8")

    assert injection.count("INSERT eval.integration_messages") == 2
    assert "COUNT(*) FROM eval.integration_messages" in verification
    assert "<> 2" in verification
