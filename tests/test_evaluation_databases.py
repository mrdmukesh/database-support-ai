from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from evaluation.framework.scenario_loader import load_scenarios

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ("payroll", "clinic", "orders", "banking", "shipping")
DATABASES = {
    "payroll": "EvalPayroll",
    "clinic": "EvalClinic",
    "orders": "EvalOrders",
    "banking": "EvalBanking",
    "shipping": "EvalShipping",
}


@pytest.mark.parametrize("domain", DOMAINS)
def test_database_package_has_required_azure_sql_objects(domain: str) -> None:
    folder = ROOT / "evaluation_databases" / domain
    create = (folder / "sql" / "01_create.sql").read_text(encoding="utf-8")
    for filename in (
        "01_create.sql",
        "02_seed.sql",
        "03_validate.sql",
        "04_reset.sql",
        "05_destroy.sql",
    ):
        assert (folder / "sql" / filename).is_file()
    table_count = len(re.findall(r"CREATE TABLE eval\.\[", create))
    if domain == "shipping":
        assert table_count >= 30
    else:
        assert 12 <= table_count <= 20
    assert len(re.findall(r"CREATE VIEW eval\.", create)) >= 5
    assert len(re.findall(r"CREATE PROCEDURE eval\.", create)) >= 8
    assert "CREATE FUNCTION eval." in create
    assert "CREATE TRIGGER eval." in create
    assert "REFERENCES eval." in create
    assert "CREATE INDEX IX_" in create
    assert "answer" not in create.lower()


@pytest.mark.parametrize("domain", DOMAINS)
def test_each_domain_has_twenty_five_complete_valid_scenarios(domain: str) -> None:
    manifest = load_scenarios(ROOT / "evaluation_scenarios" / domain / "scenarios.json")
    assert len(manifest) == 25
    assert len({scenario.scenario_id for scenario in manifest}) == 25
    assert sum("-pilot-" in scenario.scenario_id for scenario in manifest) == 5
    assert sum("-benchmark-" in scenario.scenario_id for scenario in manifest) == 20
    for scenario in manifest:
        assert scenario.active
        assert scenario.database_engine == "sqlserver"
        assert scenario.expected_entities
        assert scenario.expected_tables
        assert scenario.required_evidence
        assert scenario.acceptable_fix_concepts
        scenario_folder = ROOT / "evaluation_scenarios" / domain / scenario.scenario_id
        assert (
            json.loads((scenario_folder / "scenario.json").read_text())["scenario_id"]
            == scenario.scenario_id
        )
        for filename in (
            "baseline_reset.sql",
            "inject.sql",
            "precondition.sql",
            "verify.sql",
            "cleanup.sql",
        ):
            script = scenario_folder / filename
            assert script.is_file()
            for line in script.read_text(encoding="utf-8").splitlines():
                assert not re.search(r"\S+\s+GO\s*$", line, re.IGNORECASE), (
                    f"sqlcmd batch separator must be on its own line: {script}"
                )


def test_shipping_manifest_contains_requested_pilot_scenarios_and_lifecycle() -> None:
    scenarios = load_scenarios(ROOT / "evaluation_scenarios/shipping/scenarios.json")
    questions = " ".join(item.question.lower() for item in scenarios)
    for phrase in (
        "empty-return work order missing",
        "duplicate terminal gate event",
        "wrong carrier",
        "remain in transit",
        "enough evidence",
    ):
        assert phrase in questions
    seed = (ROOT / "evaluation_databases/shipping/sql/02_seed.sql").read_text(encoding="utf-8")
    lifecycle = (
        "Booking",
        "Container Assignment",
        "Empty Release",
        "Empty Gate Out",
        "Stuffing",
        "Export Gate In",
        "Vessel Load",
        "Vessel Departure",
        "Transshipment",
        "Import Discharge",
        "Import Gate Out",
        "Delivery",
        "Empty Return Instruction",
        "Empty Gate In",
        "Inspection",
        "Reusable Status",
    )
    assert all(stage in seed for stage in lifecycle)


@pytest.mark.parametrize("domain", DOMAINS)
def test_scenario_markers_are_isolated_and_cleanup_matches_injection(domain: str) -> None:
    markers: set[str] = set()
    for scenario in load_scenarios(ROOT / "evaluation_scenarios" / domain / "scenarios.json"):
        folder = ROOT / "evaluation_scenarios" / domain / scenario.scenario_id
        inject = (folder / "inject.sql").read_text(encoding="utf-8")
        verify = (folder / "verify.sql").read_text(encoding="utf-8")
        cleanup = (folder / "cleanup.sql").read_text(encoding="utf-8")
        marker = scenario.required_evidence[0]
        assert marker not in markers
        markers.add(marker)
        assert marker in inject and marker in verify and marker in cleanup
        assert "THROW" in verify


def _sqlcmd(database: str, script: Path) -> None:
    server = os.environ["EVAL_SQL_SERVER"]
    admin = os.environ["EVAL_SQL_ADMIN"]
    password = os.environ["EVAL_SQL_PASSWORD"]
    subprocess.run(
        [
            "sqlcmd",
            "-S",
            server,
            "-U",
            admin,
            "-P",
            password,
            "-C",
            "-b",
            "-d",
            database,
            "-i",
            str(script),
        ],
        cwd=script.parent,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(
    os.getenv("EVALUATION_SQLSERVER_INTEGRATION") != "1",
    reason="Set EVALUATION_SQLSERVER_INTEGRATION=1 with disposable SQL Server credentials",
)
@pytest.mark.parametrize("domain", DOMAINS)
def test_live_database_baseline_injection_reproduction_reset_and_isolation(domain: str) -> None:
    database = DATABASES[domain]
    sql = ROOT / "evaluation_databases" / domain / "sql"
    _sqlcmd(database, sql / "05_destroy.sql")
    _sqlcmd(database, sql / "01_create.sql")
    _sqlcmd(database, sql / "02_seed.sql")
    _sqlcmd(database, sql / "03_validate.sql")
    for scenario in load_scenarios(ROOT / "evaluation_scenarios" / domain / "scenarios.json"):
        folder = ROOT / "evaluation_scenarios" / domain / scenario.scenario_id
        _sqlcmd(database, folder / "precondition.sql")
        _sqlcmd(database, folder / "inject.sql")
        _sqlcmd(database, folder / "verify.sql")
        _sqlcmd(database, folder / "cleanup.sql")
        _sqlcmd(database, folder / "precondition.sql")
        _sqlcmd(database, sql / "04_reset.sql")
        _sqlcmd(database, sql / "03_validate.sql")
