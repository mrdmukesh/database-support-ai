from __future__ import annotations

from dataclasses import replace

import pytest

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.activation import (
    OrchestrationContext,
    OrchestrationMode,
    select_orchestration_mode,
    stable_rollout_bucket,
)


def settings(**updates) -> Settings:
    return replace(Settings(environment=Environment.TESTING), **updates)


def context(**updates) -> OrchestrationContext:
    return replace(
        OrchestrationContext("test", "workspace-1", "user-1", question="Investigate"),
        **updates,
    )


def test_missing_configuration_defaults_to_legacy(monkeypatch):
    for name in (
        "INVESTIGATION_ORCHESTRATOR_MODE",
        "LANGGRAPH_ENABLED",
        "LANGGRAPH_ROLLOUT_PERCENT",
        "LANGGRAPH_SHADOW_PERCENT",
    ):
        monkeypatch.delenv(name, raising=False)
    resolved = Settings.from_env()
    assert resolved.investigation_orchestrator_mode == "LEGACY"
    assert resolved.langgraph_enabled is False
    assert resolved.langgraph_rollout_percent == 0
    assert resolved.langgraph_shadow_percent == 0


@pytest.mark.parametrize("mode", ["invalid", "", "lang-graph", "unknown"])
def test_invalid_mode_never_activates_langgraph(mode):
    decision = select_orchestration_mode(
        settings(langgraph_enabled=True, investigation_orchestrator_mode=mode),
        context(),
    )
    assert decision.mode is OrchestrationMode.LEGACY


def test_disabled_flag_overrides_explicit_langgraph():
    decision = select_orchestration_mode(
        settings(
            langgraph_enabled=False,
            investigation_orchestrator_mode="LANGGRAPH",
        ),
        context(),
    )
    assert decision.mode is OrchestrationMode.LEGACY
    assert decision.reason == "langgraph_disabled"


def test_kill_switch_overrides_rollout_and_shadow():
    decision = select_orchestration_mode(
        settings(
            langgraph_enabled=True,
            langgraph_kill_switch=True,
            langgraph_rollout_percent=100,
            langgraph_shadow_percent=100,
        ),
        context(),
    )
    assert decision.mode is OrchestrationMode.LEGACY
    assert decision.kill_switch_active


def test_unauthorized_environment_and_workspace_remain_legacy():
    config = settings(
        langgraph_enabled=True,
        investigation_orchestrator_mode="LANGGRAPH",
        langgraph_allowed_environments=("staging",),
    )
    assert select_orchestration_mode(config, context()).reason == "environment_not_allowed"
    config = replace(
        config,
        langgraph_allowed_environments=("test",),
        langgraph_allowed_workspace_ids=("another",),
    )
    assert select_orchestration_mode(config, context()).reason == "workspace_not_allowed"


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("LEGACY", OrchestrationMode.LEGACY),
        ("LANGGRAPH", OrchestrationMode.LANGGRAPH),
        ("SHADOW", OrchestrationMode.SHADOW),
        ("COMPARE", OrchestrationMode.COMPARE),
        ("DISABLED", OrchestrationMode.DISABLED),
    ],
)
def test_explicit_authorized_modes(mode, expected):
    decision = select_orchestration_mode(
        settings(langgraph_enabled=True, investigation_orchestrator_mode=mode),
        context(),
    )
    assert decision.mode is expected


def test_compare_is_restricted_outside_lower_environments():
    decision = select_orchestration_mode(
        settings(
            langgraph_enabled=True,
            investigation_orchestrator_mode="COMPARE",
            langgraph_allowed_environments=("production",),
        ),
        context(environment="production"),
    )
    assert decision.mode is OrchestrationMode.LEGACY
    assert decision.reason == "compare_not_authorized"


def test_rollout_assignment_is_stable_and_does_not_return_raw_identifiers():
    first = stable_rollout_bucket("sensitive-workspace", "sensitive-user")
    second = stable_rollout_bucket("sensitive-workspace", "sensitive-user")
    assert first == second
    assert 0 <= first[0] < 100
    assert "sensitive" not in first[1]
    assert len(first[1]) == 64


def test_empty_rollout_key_falls_back_safely():
    bucket, key_hash = stable_rollout_bucket("", "user")
    assert bucket is None
    assert key_hash == ""


@pytest.mark.parametrize(("percentage", "mode"), [(0, "LEGACY"), (100, "LANGGRAPH")])
def test_rollout_boundaries(percentage, mode):
    decision = select_orchestration_mode(
        settings(
            langgraph_enabled=True,
            langgraph_rollout_percent=percentage,
        ),
        context(),
    )
    assert decision.mode.value == mode


def test_increasing_rollout_adds_cohorts_predictably():
    ctx = context()
    bucket, _ = stable_rollout_bucket(ctx.workspace_id, ctx.user_id)
    below = select_orchestration_mode(
        settings(langgraph_enabled=True, langgraph_rollout_percent=bucket),
        ctx,
    )
    above = select_orchestration_mode(
        settings(langgraph_enabled=True, langgraph_rollout_percent=bucket + 1),
        ctx,
    )
    assert below.mode is OrchestrationMode.LEGACY
    assert above.mode is OrchestrationMode.LANGGRAPH


def test_invalid_numeric_configuration_uses_safe_defaults(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_ROLLOUT_PERCENT", "not-a-number")
    monkeypatch.setenv("LANGGRAPH_SHADOW_PERCENT", "-50")
    monkeypatch.setenv("LANGGRAPH_TIMEOUT_SECONDS", "invalid")
    resolved = Settings.from_env()
    assert resolved.langgraph_rollout_percent == 0
    assert resolved.langgraph_shadow_percent == 0
    assert resolved.langgraph_timeout_seconds == 120.0
