from __future__ import annotations

from legacydb_copilot.routers.system import health
from legacydb_copilot.workflow.langgraph.composition import (
    register_production_langgraph_orchestrator,
)


def test_legacy_health_remains_ready_when_langgraph_is_unavailable(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_ENABLED", "false")
    monkeypatch.setenv("INVESTIGATION_ORCHESTRATOR_MODE", "LEGACY")
    register_production_langgraph_orchestrator(None)
    response = health()
    assert str(response["status"]).casefold().endswith("ok")
    assert response["langgraph"]["production_dependencies_available"] is False
    assert response["langgraph"]["orchestrator_mode"] == "LEGACY"


def test_health_reports_kill_switch_without_exposing_allowlists(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_KILL_SWITCH", "true")
    monkeypatch.setenv("LANGGRAPH_ALLOWED_WORKSPACE_IDS", "secret-workspace")
    response = health()
    assert response["langgraph"]["kill_switch_active"] is True
    assert "secret-workspace" not in str(response)
