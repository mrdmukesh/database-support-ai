from pathlib import Path

import pytest

from tools.deploy_demo_databases.demo_database_tooling import (
    INSTALL_ORDER,
    assert_approved_database,
    deployment_result,
    find_destructive_sql,
    redact,
    validate_package,
)


def _package(tmp_path: Path) -> Path:
    databases = {
        "DemoBankingV2": "Banking",
        "DemoPayrollV2": "Payroll",
        "DemoOrdersV2": "Orders",
        "DemoShippingV2": "Shipping",
        "DemoClinicV2": "Clinic",
    }
    import json

    for metadata in ("manifest.json", "ValidationReport.json"):
        (tmp_path / metadata).write_text(json.dumps({"databases": {name: {} for name in databases}}))
    for database, folder in databases.items():
        target = tmp_path / folder
        target.mkdir()
        (target / "CreateDatabase.sql").write_text(f"CREATE DATABASE [{database}];")
        for script in INSTALL_ORDER:
            (target / script).write_text(f"USE [{database}];\nSELECT 1;")
    return tmp_path


def test_valid_package_and_safe_order(tmp_path: Path) -> None:
    assert validate_package(_package(tmp_path))["status"] == "PASS"
    assert INSTALL_ORDER[-2:] == ("Functions.sql", "Triggers.sql")


def test_old_name_and_invalid_json_detection(tmp_path: Path) -> None:
    package = _package(tmp_path)
    (package / "manifest.json").write_text("{")
    (package / "Banking" / "Tables.sql").write_text("USE [DemoBankingV2]; SELECT 'EvalBanking';")
    result = validate_package(package)
    assert result["status"] == "FAIL"
    assert any("invalid JSON" in item for item in result["failures"])
    assert any("legacy database" in item for item in result["failures"])


@pytest.mark.parametrize("sql", ["DROP DATABASE x", "ALTER DATABASE x SET SINGLE_USER", "ROLLBACK IMMEDIATE"])
def test_destructive_sql_rejected(sql: str) -> None:
    assert find_destructive_sql(sql)


def test_allowlist_and_existing_database_protection() -> None:
    with pytest.raises(ValueError):
        assert_approved_database("Production")
    assert deployment_result("DemoClinicV2", exists=True, what_if=False)["status"] == "SKIPPED_ALREADY_EXISTS"
    assert deployment_result("DemoClinicV2", exists=False, what_if=True)["status"] == "WOULD_CREATE"


def test_credential_redaction() -> None:
    output = redact("password=secret authorization:BearerToken SQLCMDPASSWORD=hunter2")
    assert "secret" not in output and "BearerToken" not in output and "hunter2" not in output


def test_partial_failure_is_reportable() -> None:
    result = {"database": "DemoOrdersV2", "status": "FAILED", "error": "[REDACTED_ERROR]"}
    assert result["status"] == "FAILED"
    assert "secret" not in str(result)

