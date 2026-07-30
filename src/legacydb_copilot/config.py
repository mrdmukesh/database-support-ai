from __future__ import annotations

import os
from dataclasses import dataclass

from legacydb_copilot.common import Environment
from legacydb_copilot.services.llm_model_configuration import (
    DEFAULT_LLM_MODEL,
    normalize_reasoning_effort,
    safe_model_selection,
)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value


def _env_float(name: str, default: float, *, minimum: float = 0.1) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    )


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
    llm_reasoning_model: str = "gpt-4.1-mini"
    llm_fallback_model: str | None = "gpt-4.1-mini"
    llm_reasoning_effort: str = "medium"
    llm_max_output_tokens: int = 4000
    llm_provider_timeout_seconds: float = 60.0
    llm_model_access_verified: bool = False
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    llm_request_timeout_seconds: float = 60.0
    llm_retry_attempts: int = 2
    llm_retry_backoff_seconds: float = 0.5
    llm_retry_jitter_seconds: float = 0.25
    llm_total_timeout_seconds: float = 125.0
    llm_input_cost_per_million: float = 0.0
    llm_output_cost_per_million: float = 0.0
    llm_circuit_breaker_threshold: int = 5
    llm_circuit_breaker_cooldown_seconds: float = 30.0
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
    feature_agentic_investigation_enabled: bool = False
    agentic_max_iterations: int = 8
    agentic_max_sql_queries: int = 16
    agentic_max_total_rows: int = 1000
    agentic_max_execution_seconds: float = 120.0
    agentic_max_llm_calls: int = 8
    agentic_max_tokens: int = 32000
    agentic_max_retries: int = 1
    llm_audit_retention_days: int = 365
    azure_key_vault_url: str | None = None
    investigation_orchestrator_mode: str = "LEGACY"
    langgraph_enabled: bool = False
    langgraph_fallback_to_legacy: bool = True
    langgraph_shadow_percent: int = 0
    langgraph_rollout_percent: int = 0
    langgraph_shadow_llm_enabled: bool = False
    langgraph_compare_persist_results: bool = True
    langgraph_kill_switch: bool = False
    langgraph_allowed_environments: tuple[str, ...] = (
        "development",
        "test",
        "testing",
        "staging",
    )
    langgraph_allowed_workspace_ids: tuple[str, ...] = ()
    langgraph_allowed_user_ids: tuple[str, ...] = ()
    langgraph_max_concurrent_runs: int = 2
    langgraph_timeout_seconds: float = 120.0
    langgraph_shadow_timeout_seconds: float = 120.0
    langgraph_fallback_on_timeout: bool = True
    langgraph_fallback_on_provider_failure: bool = False
    langgraph_fallback_on_persistence_failure: bool = False
    langgraph_fallback_on_validation_failure: bool = True
    langgraph_compare_response_source: str = "legacy"

    @property
    def selected_reasoning_model(self) -> str:
        if self.llm_reasoning_model != DEFAULT_LLM_MODEL:
            return self.llm_reasoning_model
        return self.llm_model

    @property
    def selected_provider_timeout_seconds(self) -> float:
        if self.llm_provider_timeout_seconds != 60.0:
            return self.llm_provider_timeout_seconds
        return self.llm_request_timeout_seconds

    @classmethod
    def from_env(cls) -> Settings:
        environment = Environment(os.getenv("APP_ENV", Environment.DEVELOPMENT))
        environment_default = (
            DEFAULT_LLM_MODEL
            if environment in {Environment.DEVELOPMENT, Environment.TESTING}
            else "gpt-5.1"
        )
        requested_model = os.getenv(
            "LLM_REASONING_MODEL", os.getenv("LLM_MODEL", environment_default)
        )
        fallback_raw = os.getenv("LLM_FALLBACK_MODEL")
        fallback = DEFAULT_LLM_MODEL if fallback_raw is None else fallback_raw
        selected_model, selected_fallback = safe_model_selection(requested_model, fallback)
        return cls(
            environment=environment,
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
            llm_model=selected_model,
            llm_reasoning_model=selected_model,
            llm_fallback_model=selected_fallback,
            llm_reasoning_effort=normalize_reasoning_effort(
                os.getenv("LLM_REASONING_EFFORT", "medium")
            ),
            llm_max_output_tokens=_env_int(
                "LLM_MAX_OUTPUT_TOKENS", 4000, minimum=1, maximum=128000
            ),
            llm_provider_timeout_seconds=_env_float(
                "LLM_PROVIDER_TIMEOUT_SECONDS",
                _env_float("LLM_REQUEST_TIMEOUT_SECONDS", 60.0),
            ),
            llm_model_access_verified=_env_bool("LLM_MODEL_ACCESS_VERIFIED", False),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_request_timeout_seconds=float(
                os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "60")
            ),
            llm_retry_attempts=max(1, int(os.getenv("LLM_RETRY_ATTEMPTS", "2"))),
            llm_retry_backoff_seconds=max(0.0, float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "0.5"))),
            llm_retry_jitter_seconds=max(0.0, float(os.getenv("LLM_RETRY_JITTER_SECONDS", "0.25"))),
            llm_total_timeout_seconds=max(
                0.1, float(os.getenv("LLM_TOTAL_TIMEOUT_SECONDS", "125"))
            ),
            llm_input_cost_per_million=max(0.0, float(os.getenv("LLM_INPUT_COST_PER_MILLION", "0"))),
            llm_output_cost_per_million=max(0.0, float(os.getenv("LLM_OUTPUT_COST_PER_MILLION", "0"))),
            llm_circuit_breaker_threshold=max(1, int(os.getenv("LLM_CIRCUIT_BREAKER_THRESHOLD", "5"))),
            llm_circuit_breaker_cooldown_seconds=max(
                0.1, float(os.getenv("LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "30"))
            ),
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
            feature_agentic_investigation_enabled=os.getenv(
                "FEATURE_AGENTIC_INVESTIGATION_ENABLED",
                "false",
            ).lower()
            in {"1", "true", "yes", "on"},
            agentic_max_iterations=max(1, int(os.getenv("AGENTIC_MAX_ITERATIONS", "8"))),
            agentic_max_sql_queries=max(1, int(os.getenv("AGENTIC_MAX_SQL_QUERIES", "16"))),
            agentic_max_total_rows=max(1, int(os.getenv("AGENTIC_MAX_TOTAL_ROWS", "1000"))),
            agentic_max_execution_seconds=max(
                0.1, float(os.getenv("AGENTIC_MAX_EXECUTION_SECONDS", "120"))
            ),
            agentic_max_llm_calls=max(0, int(os.getenv("AGENTIC_MAX_LLM_CALLS", "8"))),
            agentic_max_tokens=max(0, int(os.getenv("AGENTIC_MAX_TOKENS", "32000"))),
            agentic_max_retries=max(0, int(os.getenv("AGENTIC_MAX_RETRIES", "1"))),
            llm_audit_retention_days=max(1, int(os.getenv("LLM_AUDIT_RETENTION_DAYS", "365"))),
            azure_key_vault_url=os.getenv("AZURE_KEY_VAULT_URL") or None,
            investigation_orchestrator_mode=os.getenv(
                "INVESTIGATION_ORCHESTRATOR_MODE", "LEGACY"
            ).strip().upper(),
            langgraph_enabled=_env_bool("LANGGRAPH_ENABLED", False),
            langgraph_fallback_to_legacy=_env_bool("LANGGRAPH_FALLBACK_TO_LEGACY", True),
            langgraph_shadow_percent=_env_int(
                "LANGGRAPH_SHADOW_PERCENT", 0, maximum=100
            ),
            langgraph_rollout_percent=_env_int(
                "LANGGRAPH_ROLLOUT_PERCENT", 0, maximum=100
            ),
            langgraph_shadow_llm_enabled=_env_bool(
                "LANGGRAPH_SHADOW_LLM_ENABLED", False
            ),
            langgraph_compare_persist_results=_env_bool(
                "LANGGRAPH_COMPARE_PERSIST_RESULTS", True
            ),
            langgraph_kill_switch=_env_bool("LANGGRAPH_KILL_SWITCH", False),
            langgraph_allowed_environments=_env_csv(
                "LANGGRAPH_ALLOWED_ENVIRONMENTS", "development,test,testing,staging"
            ),
            langgraph_allowed_workspace_ids=_env_csv(
                "LANGGRAPH_ALLOWED_WORKSPACE_IDS"
            ),
            langgraph_allowed_user_ids=_env_csv("LANGGRAPH_ALLOWED_USER_IDS"),
            langgraph_max_concurrent_runs=_env_int(
                "LANGGRAPH_MAX_CONCURRENT_RUNS", 2, minimum=1
            ),
            langgraph_timeout_seconds=_env_float("LANGGRAPH_TIMEOUT_SECONDS", 120.0),
            langgraph_shadow_timeout_seconds=_env_float(
                "LANGGRAPH_SHADOW_TIMEOUT_SECONDS", 120.0
            ),
            langgraph_fallback_on_timeout=_env_bool(
                "LANGGRAPH_FALLBACK_ON_TIMEOUT", True
            ),
            langgraph_fallback_on_provider_failure=_env_bool(
                "LANGGRAPH_FALLBACK_ON_PROVIDER_FAILURE", False
            ),
            langgraph_fallback_on_persistence_failure=_env_bool(
                "LANGGRAPH_FALLBACK_ON_PERSISTENCE_FAILURE", False
            ),
            langgraph_fallback_on_validation_failure=_env_bool(
                "LANGGRAPH_FALLBACK_ON_VALIDATION_FAILURE", True
            ),
            langgraph_compare_response_source=(
                "langgraph"
                if os.getenv(
                    "LANGGRAPH_COMPARE_RESPONSE_SOURCE", "legacy"
                ).strip().casefold()
                == "langgraph"
                else "legacy"
            ),
        )
