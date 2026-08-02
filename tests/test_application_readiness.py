from __future__ import annotations

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.services.readiness_service import application_readiness


def settings(**updates) -> Settings:
    values = {
        "environment": Environment.TESTING,
        "ai_reasoning_enabled": False,
        "langgraph_enabled": False,
    }
    values.update(updates)
    return Settings(**values)


def test_readiness_fails_when_database_dependency_is_missing():
    def unavailable(_url):
        raise ConnectionError("password=must-not-leak")

    snapshot = application_readiness(
        settings(),
        langgraph_available=False,
        database_probe=unavailable,
    )

    assert snapshot.ready is False
    assert "must-not-leak" not in str(snapshot.to_dict())
    assert next(item for item in snapshot.checks if item.name == "database").ready is False


def test_readiness_detects_migration_mismatch():
    snapshot = application_readiness(
        settings(),
        langgraph_available=False,
        database_probe=lambda _url: ("0020", "0021"),
    )

    assert snapshot.ready is False
    assert next(item for item in snapshot.checks if item.name == "migrations").ready is False


def test_legacy_readiness_allows_disabled_langgraph_composition():
    snapshot = application_readiness(
        settings(),
        langgraph_available=False,
        database_probe=lambda _url: ("0021", "0021"),
    )

    assert snapshot.ready is True


def test_enabled_langgraph_requires_registered_composition():
    snapshot = application_readiness(
        settings(langgraph_enabled=True),
        langgraph_available=False,
        database_probe=lambda _url: ("0021", "0021"),
    )

    assert snapshot.ready is False
    graph = next(item for item in snapshot.checks if item.name == "langgraph_composition")
    assert graph.detail == "required but unavailable"


def test_invalid_model_configuration_fails_readiness():
    snapshot = application_readiness(
        settings(llm_reasoning_model="invalid model identifier"),
        langgraph_available=False,
        database_probe=lambda _url: ("0021", "0021"),
    )

    assert snapshot.ready is False
