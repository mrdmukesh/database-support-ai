from __future__ import annotations

import re
from pathlib import Path

import pytest

from evaluation.demo_payroll_config import (
    DEMO_PAYROLL_DATABASE,
    DEMO_PAYROLL_DOMAIN,
    EvaluationFaultHarness,
    EvaluationFaultMode,
    FocusedReleaseThreshold,
    build_demo_payroll_lifecycle,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_ROOT = ROOT / "evaluation_databases" / "demo_payroll" / "sql"
DEPLOY_PATH = ROOT / "evaluation_databases" / "deploy-demo-payroll.ps1"


def test_isolated_database_package_has_complete_repeatable_lifecycle() -> None:
    scripts = {
        name: (SQL_ROOT / name).read_text(encoding="utf-8")
        for name in (
            "01_create.sql",
            "02_seed.sql",
            "03_validate.sql",
            "04_reset.sql",
            "05_destroy.sql",
            "06_configure_reader.sql",
        )
    }

    assert DEMO_PAYROLL_DOMAIN == "demo_payroll"
    assert DEMO_PAYROLL_DATABASE == "EvalDemoPayrollV2"
    assert "DB_NAME() <> N'EvalDemoPayrollV2'" in scripts["01_create.sql"]
    assert "DB_NAME() <> N'EvalDemoPayrollV2'" in scripts["02_seed.sql"]
    assert "DB_NAME() <> N'EvalDemoPayrollV2'" in scripts["03_validate.sql"]
    assert "DB_NAME() <> N'EvalDemoPayrollV2'" in scripts["04_reset.sql"]
    assert "DB_NAME() <> N'EvalDemoPayrollV2'" in scripts["05_destroy.sql"]
    assert "evaluation marker missing" in scripts["04_reset.sql"].casefold()
    assert "evaluation marker missing" in scripts["05_destroy.sql"].casefold()
    assert ":r 02_seed.sql" in scripts["04_reset.sql"]
    assert "evaluation_marker" in scripts["01_create.sql"]
    assert "evaluation_marker" in scripts["03_validate.sql"]
    assert "DROP DATABASE" not in " ".join(scripts.values()).upper()


def test_fixture_covers_valid_null_ambiguous_and_relationship_cases() -> None:
    create = (SQL_ROOT / "01_create.sql").read_text(encoding="utf-8")
    seed = (SQL_ROOT / "02_seed.sql").read_text(encoding="utf-8")

    assert re.search(r"DateOfBirth\s+DATE\s+NULL", create, re.I)
    assert "FK_Employee_Department" in create
    assert "FK_PayrollItem_Employee" in create
    assert "N'VAL-2001'" in seed
    assert "N'NUL-2002'" in seed
    assert {value for value in re.findall(r"N'(AMB-3001-[AB])'", seed)} == {
        "AMB-3001-A",
        "AMB-3001-B",
    }


def test_permission_fixture_denies_only_explicit_fault_object() -> None:
    permission_sql = (SQL_ROOT / "06_configure_reader.sql").read_text(
        encoding="utf-8"
    )

    assert "GRANT SELECT ON SCHEMA::dbo" in permission_sql
    assert "DENY SELECT ON OBJECT::fault.DeniedEvidence" in permission_sql
    assert "GRANT INSERT" not in permission_sql
    assert "GRANT UPDATE" not in permission_sql
    assert "GRANT DELETE" not in permission_sql
    assert "GRANT ALTER" not in permission_sql
    assert "GRANT CONTROL" not in permission_sql


def test_provider_timeout_fault_is_explicit_and_does_not_delegate() -> None:
    called = False

    def provider():
        nonlocal called
        called = True
        return {"status": "completed"}

    harness = EvaluationFaultHarness(EvaluationFaultMode.PROVIDER_TIMEOUT)
    with pytest.raises(TimeoutError, match="evaluation harness"):
        harness.provider_call(provider)

    assert called is False


def test_no_fault_delegates_normally() -> None:
    harness = EvaluationFaultHarness()

    assert harness.provider_call(lambda: {"status": "completed"}) == {
        "status": "completed"
    }
    assert harness.use_denied_permission_fixture is False


def test_fault_and_threshold_configuration_are_environment_driven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_PAYROLL_FAULT_MODE", "permission_denied")
    monkeypatch.setenv("DEMO_PAYROLL_MINIMUM_AVERAGE_SCORE", "85")
    monkeypatch.setenv("DEMO_PAYROLL_MINIMUM_EXACT_PASS_RATE", "0.9")

    fault = EvaluationFaultHarness.from_env()
    threshold = FocusedReleaseThreshold.from_env()

    assert fault.use_denied_permission_fixture is True
    assert threshold.minimum_average_score == 85
    assert threshold.minimum_exact_pass_rate == 0.9
    assert threshold.maximum_execution_failures == 0
    assert threshold.maximum_automatic_failures == 0
    assert threshold.require_all_critical_safety_gates is True


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DEMO_PAYROLL_MINIMUM_AVERAGE_SCORE", "101"),
        ("DEMO_PAYROLL_MINIMUM_EXACT_PASS_RATE", "1.1"),
        ("DEMO_PAYROLL_MAXIMUM_EXECUTION_FAILURES", "-1"),
        ("DEMO_PAYROLL_MAXIMUM_AUTOMATIC_FAILURES", "-1"),
        ("DEMO_PAYROLL_REQUIRE_ALL_SAFETY_GATES", "sometimes"),
    ],
)
def test_invalid_threshold_configuration_fails(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        FocusedReleaseThreshold.from_env()


def test_evaluation_fault_harness_is_not_imported_by_product_runtime() -> None:
    production = ROOT / "src" / "legacydb_copilot"
    imports = [
        path
        for path in production.rglob("*.py")
        if "demo_payroll_config" in path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    ]

    assert imports == []


def test_lifecycle_reuses_guarded_sqlcmd_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_SQL_SERVER", "evaluation.example.test,1433")
    monkeypatch.setenv("EVAL_SQL_ADMIN", "evaluation_admin")
    monkeypatch.setenv("EVAL_SQL_PASSWORD", "not-a-real-secret")
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER",
        "dedicated_reader",
    )
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER_PASSWORD",
        "not-a-real-reader-secret",
    )
    monkeypatch.setenv(
        "EVAL_ALLOWED_SQL_HOSTS",
        "evaluation.example.test",
    )
    monkeypatch.setenv("EVAL_ALLOWED_DATABASES", "EvalDemoPayrollV2")

    lifecycle = build_demo_payroll_lifecycle()

    assert lifecycle.databases == {
        DEMO_PAYROLL_DOMAIN: DEMO_PAYROLL_DATABASE,
    }
    assert lifecycle.allowed_databases == {DEMO_PAYROLL_DATABASE}


def test_lifecycle_requires_explicit_database_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_SQL_SERVER", "evaluation.example.test,1433")
    monkeypatch.setenv("EVAL_SQL_ADMIN", "evaluation_admin")
    monkeypatch.setenv("EVAL_SQL_PASSWORD", "not-a-real-secret")
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER",
        "dedicated_reader",
    )
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER_PASSWORD",
        "not-a-real-reader-secret",
    )
    monkeypatch.setenv("EVAL_ALLOWED_SQL_HOSTS", "evaluation.example.test")
    monkeypatch.setenv("EVAL_ALLOWED_DATABASES", "EvalPayroll")

    with pytest.raises(ValueError, match="explicitly listed"):
        build_demo_payroll_lifecycle()


def test_lifecycle_requires_exact_host_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "EVAL_DEMO_PAYROLL_ALLOWED_SQL_HOSTS",
        raising=False,
    )
    monkeypatch.setenv("EVAL_SQL_SERVER", "evaluation.example.test,1433")
    monkeypatch.setenv("EVAL_SQL_ADMIN", "evaluation_admin")
    monkeypatch.setenv("EVAL_SQL_PASSWORD", "not-a-real-secret")
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER",
        "dedicated_reader",
    )
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER_PASSWORD",
        "not-a-real-reader-secret",
    )
    monkeypatch.setenv("EVAL_ALLOWED_SQL_HOSTS", "other.example.test")
    monkeypatch.setenv("EVAL_ALLOWED_DATABASES", "EvalDemoPayrollV2")

    with pytest.raises(ValueError, match="explicitly listed"):
        build_demo_payroll_lifecycle()


def test_lifecycle_focused_host_allowlist_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_SQL_SERVER",
        "focused.example.test,1433",
    )
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_ALLOWED_SQL_HOSTS",
        "focused.example.test",
    )
    monkeypatch.setenv("EVAL_ALLOWED_SQL_HOSTS", "other.example.test")
    monkeypatch.setenv("EVAL_SQL_ADMIN", "evaluation_admin")
    monkeypatch.setenv("EVAL_SQL_PASSWORD", "admin-secret")
    monkeypatch.setenv("EVAL_ALLOWED_DATABASES", "EvalDemoPayrollV2")
    monkeypatch.setenv("EVAL_DEMO_PAYROLL_READER", "dedicated_reader")
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER_PASSWORD",
        "reader-secret",
    )

    lifecycle = build_demo_payroll_lifecycle()

    assert lifecycle.allowed_hosts == {"focused.example.test:1433"}


def test_lifecycle_uses_general_host_allowlist_when_focused_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "EVAL_DEMO_PAYROLL_ALLOWED_SQL_HOSTS",
        raising=False,
    )
    monkeypatch.delenv("EVAL_DEMO_PAYROLL_SQL_SERVER", raising=False)
    monkeypatch.setenv("EVAL_SQL_SERVER", "general.example.test,1433")
    monkeypatch.setenv("EVAL_ALLOWED_SQL_HOSTS", "general.example.test")
    monkeypatch.setenv("EVAL_SQL_ADMIN", "evaluation_admin")
    monkeypatch.setenv("EVAL_SQL_PASSWORD", "admin-secret")
    monkeypatch.setenv("EVAL_ALLOWED_DATABASES", "EvalDemoPayrollV2")
    monkeypatch.setenv("EVAL_DEMO_PAYROLL_READER", "dedicated_reader")
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER_PASSWORD",
        "reader-secret",
    )

    lifecycle = build_demo_payroll_lifecycle()

    assert lifecycle.allowed_hosts == {"general.example.test:1433"}


@pytest.mark.parametrize("same_field", ["username", "password"])
def test_lifecycle_rejects_administrator_reader_credentials(
    monkeypatch: pytest.MonkeyPatch,
    same_field: str,
) -> None:
    monkeypatch.setenv("EVAL_SQL_SERVER", "evaluation.example.test,1433")
    monkeypatch.setenv("EVAL_SQL_ADMIN", "evaluation_admin")
    monkeypatch.setenv("EVAL_SQL_PASSWORD", "admin-secret")
    monkeypatch.setenv("EVAL_ALLOWED_SQL_HOSTS", "evaluation.example.test")
    monkeypatch.setenv("EVAL_ALLOWED_DATABASES", "EvalDemoPayrollV2")
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER",
        "evaluation_admin" if same_field == "username" else "dedicated_reader",
    )
    monkeypatch.setenv(
        "EVAL_DEMO_PAYROLL_READER_PASSWORD",
        "admin-secret" if same_field == "password" else "reader-secret",
    )

    with pytest.raises(ValueError, match="non-admin reader"):
        build_demo_payroll_lifecycle()


@pytest.mark.parametrize(
    "missing_name",
    [
        "EVAL_DEMO_PAYROLL_READER",
        "EVAL_DEMO_PAYROLL_READER_PASSWORD",
    ],
)
def test_lifecycle_requires_both_reader_settings(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
) -> None:
    settings = {
        "EVAL_SQL_SERVER": "evaluation.example.test,1433",
        "EVAL_SQL_ADMIN": "evaluation_admin",
        "EVAL_SQL_PASSWORD": "admin-secret",
        "EVAL_ALLOWED_SQL_HOSTS": "evaluation.example.test",
        "EVAL_ALLOWED_DATABASES": "EvalDemoPayrollV2",
        "EVAL_DEMO_PAYROLL_READER": "dedicated_reader",
        "EVAL_DEMO_PAYROLL_READER_PASSWORD": "reader-secret",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing_name)

    with pytest.raises(KeyError):
        build_demo_payroll_lifecycle()


def test_deployment_targets_only_isolated_database() -> None:
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "$database = 'EvalDemoPayrollV2'" in deploy
    assert "$sourceDatabase = 'DemoPayrollV2'" in deploy
    assert "-ConfirmIsolatedEvaluationTarget" in deploy
    assert "az sql db delete" not in deploy.casefold()
    assert "--name $sourceDatabase" not in deploy
    assert "-d $sourceDatabase" not in deploy
    assert "06_configure_reader.sql" in deploy
    assert "ConfigureReader" not in deploy


def test_deployment_requires_reader_settings_and_distinct_credentials() -> None:
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "EVAL_DEMO_PAYROLL_READER" in deploy
    assert "EVAL_DEMO_PAYROLL_READER_PASSWORD" in deploy
    assert "EVAL_SQL_ADMIN" in deploy
    assert "EVAL_SQL_PASSWORD" in deploy
    assert "must differ from administrator credentials" in deploy


def test_deployment_requires_exact_host_and_database() -> None:
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "$database = 'EvalDemoPayrollV2'" in deploy
    assert "$sqlHost -notin $allowedHosts" in deploy
    assert "DB_NAME() <> N'EvalDemoPayrollV2'" in deploy
    assert "EVAL_DEMO_PAYROLL_RESOURCE_GROUP" in deploy
    assert "az sql server list" not in deploy


def test_contained_reader_precedes_permission_configuration() -> None:
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    creation = deploy.index("CREATE USER ")
    validation = deploy.index("$readerConnection.Open()")
    permissions = deploy.index("06_configure_reader.sql")

    assert creation < validation < permissions


def test_existing_reader_is_validated_without_password_reset() -> None:
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "authentication_type_desc" in deploy
    assert "Existing reader principal is not a contained SQL user" in deploy
    assert "ALTER USER" not in deploy
    assert "could not be validated with the approved credential" in deploy


def test_deployment_does_not_emit_or_persist_secrets() -> None:
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    assert not re.search(r"@authArgs.*['\"]-P['\"]", deploy)
    assert "Write-Output $env:EVAL_SQL_PASSWORD" not in deploy
    assert "Write-Output $env:EVAL_DEMO_PAYROLL_READER_PASSWORD" not in deploy
    assert "Set-Content" not in deploy
    assert "Add-Content" not in deploy
    assert "Out-File" not in deploy


def test_reader_validation_aggregates_without_grouping_by_database_name() -> None:
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "DB_NAME() AS DatabaseName" in deploy
    assert "COUNT_BIG(*) AS EmployeeRowCount" in deploy
    assert not re.search(r"\bAS\s+RowCount\b", deploy, re.I)
    assert "FROM dbo.Employee" in deploy
    assert not re.search(r"GROUP\s+BY\s+DB_NAME\s*\(", deploy, re.I)
