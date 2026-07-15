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
    evaluation_service_client_id: str | None = None
    evaluation_service_client_secret: str | None = None
    evaluation_service_user_id: str | None = None
    evaluation_service_organization_id: str | None = None
    evaluation_service_workspace_id: str | None = None
    evaluation_service_token_minutes: int = 15
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
    ai_debug_trace_enabled: bool = False
    knowledge_retriever_backend: str = "local"
    embedding_provider: str = "local"
    embedding_model: str = "text-embedding-3-small"
    verification_agent_enabled: bool = True
    max_investigation_rows: int = 100
    allow_full_table_scan: bool = False
    feature_enterprise_rbac_enabled: bool = False
    feature_audit_logging_enabled: bool = True
    feature_keyvault_secrets_enabled: bool = False
    azure_key_vault_url: str | None = None

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
            evaluation_service_client_id=os.getenv("EVALUATION_SERVICE_CLIENT_ID") or None,
            evaluation_service_client_secret=os.getenv("EVALUATION_SERVICE_CLIENT_SECRET") or None,
            evaluation_service_user_id=os.getenv("EVALUATION_SERVICE_USER_ID") or None,
            evaluation_service_organization_id=os.getenv("EVALUATION_SERVICE_ORGANIZATION_ID") or None,
            evaluation_service_workspace_id=os.getenv("EVALUATION_SERVICE_WORKSPACE_ID") or None,
            evaluation_service_token_minutes=int(os.getenv("EVALUATION_SERVICE_TOKEN_MINUTES", "15")),
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
            ai_debug_trace_enabled=os.getenv("AI_DEBUG_TRACE_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"},
            knowledge_retriever_backend=os.getenv("KNOWLEDGE_RETRIEVER_BACKEND", "local").lower(),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local").lower(),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            verification_agent_enabled=os.getenv("VERIFICATION_AGENT_ENABLED", "true").lower()
            in {"1", "true", "yes", "on"},
            max_investigation_rows=int(os.getenv("MAX_INVESTIGATION_ROWS", "100")),
            allow_full_table_scan=os.getenv("ALLOW_FULL_TABLE_SCAN", "false").lower()
            in {"1", "true", "yes", "on"},
            feature_enterprise_rbac_enabled=os.getenv(
                "FEATURE_ENTERPRISE_RBAC_ENABLED",
                "false",
            ).lower()
            in {"1", "true", "yes", "on"},
            feature_audit_logging_enabled=os.getenv(
                "FEATURE_AUDIT_LOGGING_ENABLED",
                "true",
            ).lower()
            in {"1", "true", "yes", "on"},
            feature_keyvault_secrets_enabled=os.getenv(
                "FEATURE_KEYVAULT_SECRETS_ENABLED",
                "false",
            ).lower()
            in {"1", "true", "yes", "on"},
            azure_key_vault_url=os.getenv("AZURE_KEY_VAULT_URL") or None,
        )
