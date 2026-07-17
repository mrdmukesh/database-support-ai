from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.fixtures.validation import manifest_sql_consistency
from evaluation.framework.contracts import ScenarioContract
from evaluation.runners.sqlcmd_database import SqlCmdDatabaseLifecycle


def load(scenario_id: str) -> ScenarioContract:
    domain = scenario_id.split("-", 1)[0]
    rows = json.loads(Path(f"evaluation_scenarios/{domain}/scenarios.json").read_text())
    return ScenarioContract(**next(row for row in rows if row["scenario_id"] == scenario_id))


def lifecycle() -> SqlCmdDatabaseLifecycle:
    return SqlCmdDatabaseLifecycle(
        server="localhost,14333", username="evaladmin", password="secret",
        databases={"shipping": "EvalShipping"}, allowed_hosts={"localhost"},
        allowed_databases={"EvalShipping"},
    )


@pytest.mark.parametrize(
    ("output", "status"),
    [("ENTITY_NOT_FOUND|0", "ENTITY_NOT_FOUND"), ("ENTITY_FOUND|1", "ENTITY_FOUND"), ("ENTITY_DUPLICATE|2", "ENTITY_DUPLICATE")],
)
def test_exact_entity_statuses_are_enforced(monkeypatch, output, status):
    app = lifecycle()
    monkeypatch.setattr(app, "_run_query", lambda *_a, **_k: SimpleNamespace(stdout=output))
    result = app._verify_entity(load("shipping-pilot-001"), "evalreader", "secret")
    assert result["status"] == status
    assert (result["exact_row_count"] == 1) is (status == "ENTITY_FOUND")


def test_script_success_does_not_imply_fixture_validity(monkeypatch):
    app = lifecycle()
    scenario = load("shipping-pilot-001")
    monkeypatch.setattr(app, "_run", lambda *_a, **_k: SimpleNamespace(stdout="script passed"))
    monkeypatch.setattr(app, "_verify_entity", lambda *_a, **_k: {"status": "ENTITY_NOT_FOUND"})
    monkeypatch.setattr(app, "_verify_defect_linkage", lambda *_a, **_k: {"valid": True})
    assert app.verify(scenario)["verified"] is False


def test_question_and_sql_manifest_mismatch_is_rejected(tmp_path):
    scenario = load("shipping-pilot-001")
    setup = tmp_path / "inject.sql"; setup.write_text("SELECT 'OTHER-1'", encoding="utf-8")
    invalid = replace(scenario, setup_script=str(setup))
    result = manifest_sql_consistency(invalid)
    assert result["status"] == "FIXTURE_MANIFEST_MISMATCH"
    assert any("setup SQL" in reason for reason in result["reasons"])


def test_message_and_correlation_ids_cannot_be_business_keys():
    scenario = load("shipping-pilot-001")
    for value in ("MSG-SHP-5001", "CORR-SHP-5001"):
        result = manifest_sql_consistency(replace(scenario, expected_entity_value=value, expected_entity_question_value=value))
        assert not result["consistent"]
        assert any("diagnostic/message prefix" in reason for reason in result["reasons"])


def test_application_credentials_must_see_entity(monkeypatch):
    app = lifecycle(); scenario = load("shipping-pilot-001")
    monkeypatch.setattr(app, "_run", lambda *_a, **_k: SimpleNamespace(stdout="script passed"))
    monkeypatch.setattr(app, "_verify_defect_linkage", lambda *_a, **_k: {"valid": True})
    monkeypatch.setattr(app, "_verify_entity", lambda _s, user, _p: {"status": "ENTITY_FOUND" if user == "evaladmin" else "ENTITY_QUERY_FAILED"})
    assert app.verify(scenario)["verified"] is False


@pytest.mark.parametrize("scenario_id,value,table", [
    ("shipping-pilot-001", "SHP-5001", "shipments"),
    ("banking-pilot-001", "TRF-3101", "transfers"),
    ("orders-pilot-001", "ORD-7101", "sales_orders"),
    ("payroll-pilot-001", "EMP-1042", "employees"),
    ("clinic-pilot-001", "APT-2101", "appointments"),
])
def test_pilot_contracts_create_and_verify_exact_business_entity(scenario_id, value, table):
    scenario = load(scenario_id)
    assert scenario.expected_entity_value == value
    assert scenario.expected_entity_table == table
    assert scenario.expected_entity_match_mode == "exact"
    assert manifest_sql_consistency(scenario)["consistent"]
    assert value in Path(scenario.setup_script).read_text(encoding="utf-8")
    assert f"BusinessKey=N'{value}'" in Path(scenario.verification_script).read_text(encoding="utf-8") or f"BusinessKey='{value}'" in Path(scenario.verification_script).read_text(encoding="utf-8")


def test_all_125_contracts_have_typed_entity_metadata_and_consistent_sql():
    rows = []
    for path in Path("evaluation_scenarios").glob("*/scenarios.json"):
        rows.extend(json.loads(path.read_text(encoding="utf-8")))
    assert len(rows) == 125
    scenarios = [ScenarioContract(**row) for row in rows]
    assert all(item.expected_entity_value and item.expected_entity_table and item.expected_entity_column for item in scenarios)
    assert all(manifest_sql_consistency(item)["consistent"] for item in scenarios)


def test_no_fixture_entity_values_are_hardcoded_in_application_logic():
    production = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in Path("src").rglob("*.py"))
    for value in ("TRF-3101", "ORD-7101", "EMP-1042", "APT-2101"):
        assert value not in production
