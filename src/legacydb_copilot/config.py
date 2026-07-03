from __future__ import annotations

import os
from dataclasses import dataclass

from legacydb_copilot.common import Environment


@dataclass(frozen=True)
class Settings:
    environment: Environment
    app_name: str = "LegacyDB Support Copilot"
    database_url: str = "postgresql+psycopg://legacydb:legacydb@localhost:5432/legacydb_copilot"
    jwt_secret: str = "dev-only-change-me"
    jwt_access_token_minutes: int = 60
    session_timeout_minutes: int = 60
    upload_max_size_bytes: int = 25 * 1024 * 1024
    storage_backend: str = "local"
    local_storage_root: str = "."
    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "app-artifacts"
    sentry_dsn: str | None = None
    ai_reasoning_enabled: bool = False
    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    knowledge_retriever_backend: str = "sqlite"
    verification_agent_enabled: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            environment=Environment(os.getenv("APP_ENV", Environment.DEVELOPMENT)),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://legacydb:legacydb@localhost:5432/legacydb_copilot",
            ),
            jwt_secret=os.getenv("JWT_SECRET", "dev-only-change-me"),
            jwt_access_token_minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60")),
            session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "60")),
            upload_max_size_bytes=int(os.getenv("UPLOAD_MAX_SIZE_BYTES", str(25 * 1024 * 1024))),
            storage_backend=os.getenv("STORAGE_BACKEND", "local").lower(),
            local_storage_root=os.getenv("LOCAL_STORAGE_ROOT", "."),
            azure_storage_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING") or None,
            azure_storage_container=os.getenv("AZURE_STORAGE_CONTAINER", "app-artifacts"),
            sentry_dsn=os.getenv("SENTRY_DSN") or None,
            ai_reasoning_enabled=os.getenv(
                "AI_REASONING_ENABLED",
                os.getenv("LLM_ENABLED", "false"),
            ).lower()
            in {"1", "true", "yes", "on"},
            llm_enabled=os.getenv(
                "AI_REASONING_ENABLED",
                os.getenv("LLM_ENABLED", "false"),
            ).lower()
            in {"1", "true", "yes", "on"},
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            knowledge_retriever_backend=os.getenv("KNOWLEDGE_RETRIEVER_BACKEND", "sqlite").lower(),
            verification_agent_enabled=os.getenv("VERIFICATION_AGENT_ENABLED", "true").lower()
            in {"1", "true", "yes", "on"},
        )
