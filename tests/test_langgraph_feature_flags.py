from __future__ import annotations

from dataclasses import replace

import pytest

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.activation import (
    OrchestrationContext,
    OrchestrationMode,
    select_orchestration_mode,
)


def context() -> OrchestrationContext:
    return OrchestrationContext("production", "workspace", "user")


def test_missing_configuration_defaults_to_langgraph(monkeypatch):
    for name in (
        "INVESTIGATION_ORCHESTRATOR_MODE",
        "LANGGRAPH_ENABLED",
        "LANGGRAPH_FALLBACK_TO_LEGACY",
    ):
        monkeypatch.delenv(name, raising=False)
    resolved = Settings.from_env()
    assert resolved.investigation_orchestrator_mode == "LANGGRAPH"
    assert resolved.langgraph_enabled is True
    assert resolved.langgraph_fallback_to_legacy is False


@pytest.mark.parametrize("mode", ["LEGACY", "AUTO", "SHADOW", "COMPARE", "DISABLED", "invalid", ""])
def test_all_configured_modes_are_ignored(mode):
    settings = replace(
        Settings(environment=Environment.TESTING),
        investigation_orchestrator_mode=mode,
        langgraph_enabled=False,
        langgraph_kill_switch=True,
        langgraph_rollout_percent=0,
        langgraph_allowed_environments=(),
        langgraph_allowed_workspace_ids=("other",),
        langgraph_allowed_user_ids=("other",),
    )
    decision = select_orchestration_mode(settings, context())
    assert decision.mode is OrchestrationMode.LANGGRAPH
    assert decision.reason == "langgraph_only"
    assert decision.cohort is None
    assert decision.rollout_key_hash == ""
    assert decision.kill_switch_active is False


def test_environment_values_cannot_override_langgraph_only(monkeypatch):
    monkeypatch.setenv("INVESTIGATION_ORCHESTRATOR_MODE", "LEGACY")
    monkeypatch.setenv("LANGGRAPH_ENABLED", "false")
    monkeypatch.setenv("LANGGRAPH_FALLBACK_TO_LEGACY", "true")
    resolved = Settings.from_env()
    assert resolved.investigation_orchestrator_mode == "LANGGRAPH"
    assert resolved.langgraph_enabled is True
    assert resolved.langgraph_fallback_to_legacy is False
