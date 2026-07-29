from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.demo_payroll_benchmark.loader import (
    DATABASE,
    load_focused_pack,
    validate_focused_pack,
)


def test_focused_pack_has_five_isolated_reader_scenarios() -> None:
    manifest, truth, scenarios, payload = load_focused_pack()

    validate_focused_pack(payload, "reader-connection")
    assert len(manifest) == len(truth) == len(scenarios) == 5
    assert {item.database for item in manifest} == {DATABASE}
    assert all(
        item["connection_env"] == "EVAL_DEMO_PAYROLL_CONNECTION_ID"
        for item in payload
    )


def test_focused_pack_excludes_denied_and_mutating_objects() -> None:
    _manifest, _truth, _scenarios, payload = load_focused_pack()
    serialized = json.dumps(payload)

    assert "fault.DeniedEvidence" not in serialized
    assert not any(
        token in item["question"].upper()
        for item in payload
        for token in ("INSERT ", "UPDATE ", "DELETE ", "MERGE ", "DROP ", "ALTER ")
    )


def test_manifest_rejects_missing_connection() -> None:
    payload = json.loads(
        (
            Path("evaluation/demo_payroll_benchmark") / "manifest.json"
        ).read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="CONNECTION_ID"):
        validate_focused_pack(payload, "")


def test_nonexistent_and_null_cases_prohibit_invention() -> None:
    _manifest, _truth, _scenarios, payload = load_focused_pack()
    indexed = {item["scenario_id"]: item for item in payload}

    assert "invented age" in indexed["demo-payroll-focused-002"]["prohibited_claims"]
    assert (
        "invented employee details"
        in indexed["demo-payroll-focused-004"]["prohibited_claims"]
    )
