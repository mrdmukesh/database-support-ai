from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from legacydb_copilot.services.environment_resolution_service import (
    EnvironmentResolutionError,
    EnvironmentSnapshot,
    EnvironmentType,
    SafetyProfile,
    resolve_environment,
)
from legacydb_copilot.services.scan_policy_service import ScanPolicyService


def connection(environment: str | None = "test"):
    return SimpleNamespace(
        id="639ebe0b-f508-4f32-88e4-0dd7df8f2ece",
        name="Test_Payrool",
        database_name="DemoPayrollV2",
        environment_type=environment,
    )


@pytest.mark.parametrize("environment", ["test", "demo"])
def test_test_and_demo_resolve_to_nonproduction_deep_read_only(environment: str) -> None:
    result = resolve_environment(
        connection(environment), workspace_id="Demo_Databases", request_environment=environment
    )
    assert result.snapshot.safety_profile == SafetyProfile.NON_PRODUCTION_DEEP_READ_ONLY
    assert result.snapshot.procedure_execution_permitted is True
    assert result.snapshot.data_modification_permitted is False


def test_production_resolves_to_strict_read_only() -> None:
    result = resolve_environment(
        connection("production"), workspace_id="WS", request_environment="PRODUCTION"
    )
    assert result.snapshot.environment_type == EnvironmentType.PRODUCTION
    assert result.snapshot.safety_profile == SafetyProfile.PRODUCTION_STRICT_READ_ONLY
    assert result.snapshot.procedure_execution_permitted is False


def test_missing_registered_environment_and_conflict_are_blocked() -> None:
    with pytest.raises(EnvironmentResolutionError, match="metadata is missing"):
        resolve_environment(connection(None), workspace_id="WS", request_environment="test")
    with pytest.raises(EnvironmentResolutionError, match="Environment mismatch"):
        resolve_environment(connection("production"), workspace_id="WS", request_environment="test")


def test_snapshot_survives_json_worker_dispatch_without_name_inference() -> None:
    resolved = resolve_environment(
        connection(), workspace_id="Demo_Databases", request_environment="TEST"
    )
    payload = json.loads(json.dumps(resolved.snapshot.to_dict()))
    worker_snapshot = EnvironmentSnapshot(
        selected_connection_id=payload["selected_connection_id"],
        selected_database_name=payload["selected_database_name"],
        workspace_id=payload["workspace_id"],
        environment_type=EnvironmentType(payload["environment_type"]),
        safety_profile=SafetyProfile(payload["safety_profile"]),
        environment_source=payload["environment_source"],
        procedure_execution_permitted=payload["procedure_execution_permitted"],
        data_modification_permitted=payload["data_modification_permitted"],
    )
    assert worker_snapshot == resolved.snapshot
    assert worker_snapshot.selected_connection_id == connection().id


def test_scan_policy_exposes_required_safety_profiles() -> None:
    service = ScanPolicyService()
    assert service.resolve_policy(
        environment_type="test", max_scan_rows=1000, default_max_rows=100
    ).safety_profile == "NON_PRODUCTION_DEEP_READ_ONLY"
    assert service.resolve_policy(
        environment_type="production", max_scan_rows=100, default_max_rows=100
    ).safety_profile == "PRODUCTION_STRICT_READ_ONLY"
