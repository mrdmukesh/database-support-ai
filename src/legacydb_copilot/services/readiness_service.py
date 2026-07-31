from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from legacydb_copilot.config import Settings
from legacydb_copilot.services.llm_model_configuration import (
    model_capabilities,
    normalize_model_name,
)


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    ready: bool
    detail: str


@dataclass(frozen=True)
class ReadinessSnapshot:
    ready: bool
    checks: tuple[ReadinessCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "ready" if self.ready else "not_ready",
            "checks": [
                {
                    "name": item.name,
                    "status": "ready" if item.ready else "not_ready",
                    "detail": item.detail,
                }
                for item in self.checks
            ],
        }


def application_readiness(
    settings: Settings | None = None,
    *,
    langgraph_available: bool,
    database_probe: Callable[[str], tuple[str | None, str]] | None = None,
) -> ReadinessSnapshot:
    settings = settings or Settings.from_env()
    checks: list[ReadinessCheck] = []

    def add(name: str, ready: bool, detail: str) -> None:
        checks.append(ReadinessCheck(name, ready, detail))

    try:
        if database_probe is None:
            engine = create_engine(settings.database_url, pool_pre_ping=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                current = MigrationContext.configure(connection).get_current_revision()
            head = ScriptDirectory.from_config(Config(str(Path("alembic.ini")))).get_current_head()
        else:
            current, head = database_probe(settings.database_url)
        add("database", True, "connection available")
        add(
            "migrations",
            bool(current and head and current == head),
            f"database={current or 'missing'}; code={head or 'missing'}",
        )
    except Exception as exc:
        add("database", False, f"connection failed: {type(exc).__name__}")
        add("migrations", False, "not checked")

    selected_model = settings.selected_reasoning_model
    try:
        valid_model = normalize_model_name(selected_model) is not None
        capabilities = model_capabilities(selected_model)
        provider_valid = settings.llm_provider == "openai" and capabilities.responses_api
    except ValueError:
        valid_model = provider_valid = False
    credentials_ready = not settings.ai_reasoning_enabled or bool(settings.openai_api_key)
    add(
        "model_provider_configuration",
        valid_model and provider_valid and credentials_ready,
        (
            f"provider={settings.llm_provider}; model={selected_model}; "
            f"credentials={'configured' if settings.openai_api_key else 'missing'}"
        ),
    )
    add("legacy_orchestrator", True, "available")
    graph_required = settings.langgraph_enabled
    add(
        "langgraph_composition",
        langgraph_available or not graph_required,
        (
            "available"
            if langgraph_available
            else ("unavailable but disabled" if not graph_required else "required but unavailable")
        ),
    )
    return ReadinessSnapshot(all(item.ready for item in checks), tuple(checks))
