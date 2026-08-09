from __future__ import annotations

import pytest

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.services.llm_model_configuration import build_reasoning_parameters
from legacydb_copilot.services.llm_model_preflight import run_model_access_preflight
from legacydb_copilot.workflow.langgraph.activation import (
    OrchestrationContext,
    OrchestrationMode,
    select_orchestration_mode,
)


class Provider:
    def __init__(self, response=None, failure=None):
        self.response = response
        self.failure = failure
        self.request = None

    def invoke_json(self, request):
        self.request = request
        if self.failure:
            raise self.failure
        return self.response


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ("development", "gpt-4.1-mini"),
        ("testing", "gpt-4.1-mini"),
        ("staging", "gpt-5.1"),
        ("production", "gpt-5.1"),
    ],
)
def test_environment_model_defaults(monkeypatch, environment, expected):
    monkeypatch.setenv("APP_ENV", environment)
    for name in ("LLM_REASONING_MODEL", "LLM_MODEL", "LLM_FALLBACK_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert Settings.from_env().selected_reasoning_model == expected


def test_configuration_and_invalid_candidate_use_explicit_fallback(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_MODEL", "not-a-model")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "gpt-5-mini")
    settings = Settings.from_env()
    assert settings.selected_reasoning_model == "gpt-5-mini"
    assert settings.llm_fallback_model == "gpt-5-mini"


def test_only_supported_model_parameters_are_sent():
    mini, unsupported = build_reasoning_parameters(
        model="gpt-4.1-mini", reasoning_effort="high", max_output_tokens=4000
    )
    candidate, candidate_unsupported = build_reasoning_parameters(
        model="gpt-5.1", reasoning_effort="high", max_output_tokens=4000
    )
    assert "reasoning" not in mini
    assert unsupported == ("reasoning_effort",)
    assert candidate["reasoning"] == {"effort": "high"}
    assert candidate_unsupported == ()


def test_preflight_parses_output_and_captures_telemetry_without_exposing_key():
    provider = Provider(
        {"output_text": '{"preflight":"ok"}', "usage": {"input_tokens": 10, "output_tokens": 4}}
    )
    settings = Settings(
        environment=Environment.TESTING,
        llm_reasoning_model="gpt-5.1",
        openai_api_key="super-secret",
        llm_input_cost_per_million=1,
        llm_output_cost_per_million=2,
    )
    result = run_model_access_preflight(settings, client=provider)
    assert result.passed
    assert (result.input_tokens, result.output_tokens) == (10, 4)
    assert result.estimated_cost == pytest.approx(0.000018)
    assert "super-secret" not in str(result)
    assert provider.request.timeout_seconds == 60


def test_failed_preflight_is_sanitized_and_does_not_change_workflow_engine():
    settings = Settings(
        environment=Environment.TESTING,
        ai_reasoning_enabled=True,
        langgraph_enabled=True,
        investigation_orchestrator_mode="LANGGRAPH",
        openai_api_key="super-secret",
        llm_model_access_verified=False,
    )
    result = run_model_access_preflight(
        settings, client=Provider(failure=RuntimeError("super-secret leaked"))
    )
    decision = select_orchestration_mode(
        settings,
        OrchestrationContext("test", "workspace", "user"),
    )
    assert result.error == "RuntimeError"
    assert "super-secret" not in str(result)
    assert decision.mode is OrchestrationMode.LANGGRAPH
    assert decision.reason == "langgraph_only"


def test_verified_model_access_allows_configured_langgraph_route():
    settings = Settings(
        environment=Environment.TESTING,
        ai_reasoning_enabled=True,
        langgraph_enabled=True,
        investigation_orchestrator_mode="LANGGRAPH",
        llm_model_access_verified=True,
    )
    decision = select_orchestration_mode(
        settings, OrchestrationContext("test", "workspace", "user")
    )
    assert decision.mode is OrchestrationMode.LANGGRAPH
