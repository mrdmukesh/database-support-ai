from types import SimpleNamespace

import pytest

from legacydb_copilot.common import Environment
from legacydb_copilot.services import secrets_service
from legacydb_copilot.services.secrets_service import AzureKeyVaultSecretStore, get_secret_store


class KeyVaultFailure(Exception):
    def __init__(
        self,
        status_code: int,
        content_type: str = "application/json",
        *,
        secret: str = "",
    ) -> None:
        super().__init__(f"secret lookup failed {secret}")
        self.status_code = status_code
        self.response = SimpleNamespace(headers={
            "content-type": content_type,
            "x-ms-request-id": "request-123",
            "x-ms-keyvault-region": "centralindia",
        })


def store_with_client(client) -> AzureKeyVaultSecretStore:
    store = AzureKeyVaultSecretStore.__new__(AzureKeyVaultSecretStore)
    store._client = client
    return store


def test_keyvault_retries_transient_html_400(monkeypatch) -> None:
    calls = []

    class Client:
        def get_secret(self, name):
            calls.append(name)
            if len(calls) < 3:
                raise KeyVaultFailure(400, "text/html; charset=utf-8")
            return SimpleNamespace(value="resolved-value")

    monkeypatch.setattr("legacydb_copilot.services.secrets_service.time.sleep", lambda _: None)
    assert store_with_client(Client()).get_secret("keyvault://database-connection") == "resolved-value"
    assert calls == ["database-connection"] * 3


def test_keyvault_does_not_retry_non_transient_client_error(monkeypatch) -> None:
    calls = []

    class Client:
        def get_secret(self, name):
            calls.append(name)
            raise KeyVaultFailure(403)

    monkeypatch.setattr("legacydb_copilot.services.secrets_service.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="Secure secret retrieval failed"):
        store_with_client(Client()).get_secret("keyvault://database-connection")
    assert calls == ["database-connection"]


def production_settings() -> SimpleNamespace:
    return SimpleNamespace(
        feature_keyvault_secrets_enabled=True,
        azure_key_vault_url="https://example.vault.azure.net/",
        environment=Environment.PRODUCTION,
    )


def test_process_wide_store_and_client_are_reused(monkeypatch) -> None:
    created = []

    class Store:
        pass

    def build(vault_url, *, use_managed_identity):
        created.append((vault_url, use_managed_identity))
        return Store()

    secrets_service._shared_azure_secret_store.cache_clear()
    monkeypatch.setattr(secrets_service, "AzureKeyVaultSecretStore", build)
    first = get_secret_store(production_settings())
    second = get_secret_store(production_settings())
    assert first is second
    assert created == [("https://example.vault.azure.net/", True)]
    secrets_service._shared_azure_secret_store.cache_clear()


def test_non_production_azure_store_preserves_default_credential_path(monkeypatch) -> None:
    calls = []

    def build(vault_url, *, use_managed_identity):
        calls.append((vault_url, use_managed_identity))
        return object()

    settings = production_settings()
    settings.environment = Environment.TESTING
    secrets_service._shared_azure_secret_store.cache_clear()
    monkeypatch.setattr(secrets_service, "AzureKeyVaultSecretStore", build)
    get_secret_store(settings)
    assert calls == [("https://example.vault.azure.net/", False)]
    secrets_service._shared_azure_secret_store.cache_clear()


def test_retry_backoff_is_exponential(monkeypatch) -> None:
    sleeps = []
    attempts = []

    class Client:
        def get_secret(self, name):
            attempts.append(name)
            if len(attempts) < 3:
                raise KeyVaultFailure(429)
            return SimpleNamespace(value="resolved-value")

    monkeypatch.setattr(secrets_service.time, "sleep", sleeps.append)
    assert store_with_client(Client()).get_secret("keyvault://database-connection") == "resolved-value"
    assert sleeps == [0.25, 0.5]


def test_failure_logs_only_safe_metadata(caplog) -> None:
    secret_value = "never-log-this-secret-value"

    class Client:
        def get_secret(self, name):
            raise KeyVaultFailure(403, secret=secret_value)

    with caplog.at_level("WARNING"), pytest.raises(
        RuntimeError,
        match="Secure secret retrieval failed",
    ):
        store_with_client(Client()).get_secret("keyvault://database-connection")
    assert secret_value not in caplog.text
    record = caplog.records[-1]
    assert record.key_vault_http_status == 403
    assert record.key_vault_content_type == "application/json"
    assert record.key_vault_request_id == "request-123"
    assert record.key_vault_region == "centralindia"
    assert record.key_vault_exception_class == "KeyVaultFailure"
    assert record.key_vault_retry_attempt == 1
