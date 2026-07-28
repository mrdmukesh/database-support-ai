from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from legacydb_copilot.schemas import DatabaseConnectionCreate
from legacydb_copilot.services.scan_policy_service import ScanPolicyService


@pytest.mark.parametrize(
    ("environment", "policy", "rows", "relationship_depth", "masking", "timeout"),
    [
        ("production", "production_strict", 100, 1, True, 15),
        ("uat", "uat_readonly", 500, 2, True, 30),
        ("test", "test_readonly", 1000, 3, False, 30),
        ("evaluation", "evaluation_readonly", 1000, 3, False, 30),
        ("demo", "evaluation_readonly", 1000, 3, False, 30),
    ],
)
def test_policy_matrix(
    environment: str,
    policy: str,
    rows: int,
    relationship_depth: int,
    masking: bool,
    timeout: int,
) -> None:
    resolved = ScanPolicyService().resolve_policy(
        environment_type=environment,
        max_scan_rows=None,
        default_max_rows=100,
    )

    assert resolved.name == policy
    assert resolved.max_rows == rows
    assert resolved.allow_metadata_scan is True
    assert resolved.allow_relationship_discovery is True
    assert resolved.max_relationship_depth == relationship_depth
    assert resolved.mask_sensitive_data is masking
    assert resolved.query_timeout_seconds == timeout
    assert resolved.allow_unrestricted_read_scan is False
    assert resolved.require_row_limit is True


def test_environment_validation_is_server_side_and_missing_fails_closed() -> None:
    payload = {
        "organization_id": "ORG",
        "workspace_id": "WS",
        "engine": "sql_server",
        "name": "Payroll",
        "secret_ref": "env://PAYROLL",
    }
    with pytest.raises(ValidationError):
        DatabaseConnectionCreate(**payload)

    with pytest.raises(ValidationError):
        DatabaseConnectionCreate(**payload, environment_type="this is not production")


def test_migration_persists_policy_context_without_name_inference() -> None:
    migration = Path("alembic/versions/0012_environment_aware_investigation_mode.py").read_text(
        encoding="utf-8"
    )
    assert "environment_type" in migration
    assert "policy_name" in migration
    assert "policy_version" in migration
    assert "policy_audit_json" in migration
    assert "DemoPayrollV2" not in migration
    assert "Demo_Databases" not in migration


def test_policy_and_llm_audit_models_persist_required_context() -> None:
    models = Path("src/legacydb_copilot/db/models.py").read_text(encoding="utf-8")
    for field in (
        "environment_type",
        "policy_name",
        "policy_version",
        "policy_audit_json",
        "connection_id",
    ):
        assert field in models


def test_authoritative_snapshot_migration_is_additive_and_follows_current_head() -> None:
    migration = Path(
        "alembic/versions/0016_authoritative_environment_snapshot.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "0015_safe_planner"' in migration
    for field in (
        "selected_database_name",
        "safety_profile",
        "environment_source",
        "environment_snapshot_json",
        "environment_telemetry_json",
    ):
        assert field in migration
    assert "drop_table" not in migration
    assert "DELETE FROM" not in migration
