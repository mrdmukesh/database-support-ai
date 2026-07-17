from __future__ import annotations

from legacydb_copilot.runtime_diagnostics import effective_runtime_configuration


def test_runtime_diagnostic_exposes_presence_not_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:super-secret@localhost/appdb")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("AI_REASONING_ENABLED", "true")
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("VERIFICATION_AGENT_ENABLED", "true")
    payload = effective_runtime_configuration("test")
    rendered = str(payload)
    assert payload["openai_api_key_present"] is True
    assert payload["ai_reasoning_enabled"] is True
    assert payload["llm_enabled"] is True
    assert payload["database_host"] == "localhost"
    assert payload["database_name"] == "appdb"
    assert "super-secret" not in rendered
    assert "sk-secret" not in rendered
