from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
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
    store._use_rest_for_reads = False
    return store


def store_with_rest(handler) -> AzureKeyVaultSecretStore:
    store = AzureKeyVaultSecretStore.__new__(AzureKeyVaultSecretStore)
    store._credential = SimpleNamespace(
        get_token=lambda scope: SimpleNamespace(token="never-log-access-token")
    )
    store._http_client = httpx.Client(transport=httpx.MockTransport(handler))
    store._vault_url = "https://example.vault.azure.net"
    store._use_rest_for_reads = True
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

    secrets_service._cached_azure_secret_store.cache_clear()
    monkeypatch.setattr(secrets_service, "AzureKeyVaultSecretStore", build)
    first = get_secret_store(production_settings())
    second = get_secret_store(production_settings())
    assert first is second
    assert created == [("https://example.vault.azure.net/", True)]
    secrets_service._cached_azure_secret_store.cache_clear()


def test_concurrent_first_access_creates_one_store(monkeypatch) -> None:
    created = []

    class Store:
        pass

    def build(vault_url, *, use_managed_identity):
        created.append((vault_url, use_managed_identity))
        return Store()

    secrets_service._cached_azure_secret_store.cache_clear()
    monkeypatch.setattr(secrets_service, "AzureKeyVaultSecretStore", build)
    with ThreadPoolExecutor(max_workers=8) as executor:
        stores = list(executor.map(lambda _: get_secret_store(production_settings()), range(16)))
    assert all(store is stores[0] for store in stores)
    assert created == [("https://example.vault.azure.net/", True)]
    secrets_service._cached_azure_secret_store.cache_clear()


def test_non_production_azure_store_preserves_default_credential_path(monkeypatch) -> None:
    calls = []

    def build(vault_url, *, use_managed_identity):
        calls.append((vault_url, use_managed_identity))
        return object()

    settings = production_settings()
    settings.environment = Environment.TESTING
    secrets_service._cached_azure_secret_store.cache_clear()
    monkeypatch.setattr(secrets_service, "AzureKeyVaultSecretStore", build)
    get_secret_store(settings)
    assert calls == [("https://example.vault.azure.net/", False)]
    secrets_service._cached_azure_secret_store.cache_clear()


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


def response(status: int, *, content_type: str, body: str, headers=None) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"content-type": content_type, **(headers or {})},
        text=body,
    )


def test_rest_success_returns_secret_without_logging_it(caplog) -> None:
    secret = "Server=private;Password=never-log"
    store = store_with_rest(
        lambda request: response(200, content_type="application/json", body=f'{{"value":"{secret}"}}')
    )
    with caplog.at_level("WARNING"):
        assert store.get_secret("keyvault://database-connection") == secret
    assert secret not in caplog.text
    assert "never-log-access-token" not in caplog.text


@pytest.mark.parametrize(
    ("status", "content_type", "body", "expected_attempts"),
    [
        (200, "text/html", "<html>upstream</html>", 3),
        (400, "text/html", "<html>bad gateway</html>", 3),
        (401, "application/json", '{"error":"unauthorized"}', 1),
        (403, "application/json", '{"error":"forbidden"}', 1),
        (200, "application/json", "not-json", 3),
        (200, "application/json", '{"id":"missing-value"}', 3),
    ],
)
def test_rest_response_classification_is_bounded(
    monkeypatch,
    status,
    content_type,
    body,
    expected_attempts,
) -> None:
    attempts = []
    monkeypatch.setattr(secrets_service.time, "sleep", lambda delay: None)

    def handler(request):
        attempts.append(request)
        return response(status, content_type=content_type, body=body)

    with pytest.raises(RuntimeError, match="Secure secret retrieval failed"):
        store_with_rest(handler).get_secret("keyvault://database-connection")
    assert len(attempts) == expected_attempts


def test_rest_429_respects_retry_after(monkeypatch) -> None:
    attempts = []
    sleeps = []
    monkeypatch.setattr(secrets_service.time, "sleep", sleeps.append)

    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            return response(
                429,
                content_type="application/json",
                body='{"error":"throttled"}',
                headers={"retry-after": "2"},
            )
        return response(200, content_type="application/json", body='{"value":"resolved"}')

    assert store_with_rest(handler).get_secret("keyvault://database-connection") == "resolved"
    assert sleeps == [2.0]


def test_rest_5xx_transient_failure_recovers(monkeypatch) -> None:
    attempts = []
    monkeypatch.setattr(secrets_service.time, "sleep", lambda delay: None)

    def handler(request):
        attempts.append(request)
        if len(attempts) < 3:
            return response(503, content_type="text/html", body="unavailable")
        return response(200, content_type="application/json", body='{"value":"resolved"}')

    assert store_with_rest(handler).get_secret("keyvault://database-connection") == "resolved"
    assert len(attempts) == 3


def test_rest_reuses_http_client_and_credential() -> None:
    token_scopes = []
    requests = []
    store = store_with_rest(
        lambda request: requests.append(request)
        or response(200, content_type="application/json", body='{"value":"resolved"}')
    )
    credential = SimpleNamespace(
        get_token=lambda scope: token_scopes.append(scope)
        or SimpleNamespace(token="never-log-access-token")
    )
    store._credential = credential
    client = store._http_client
    assert store.get_secret("keyvault://first") == "resolved"
    assert store.get_secret("keyvault://second") == "resolved"
    assert store._credential is credential
    assert store._http_client is client
    assert token_scopes == [secrets_service._KEY_VAULT_SCOPE] * 2
    assert len(requests) == 2
    assert requests[0].url.path == "/secrets/first"
    assert requests[0].url.params["api-version"] == "7.4"
    assert requests[0].headers["authorization"] == "Bearer never-log-access-token"


def test_rest_failure_logging_never_contains_sensitive_material(monkeypatch, caplog) -> None:
    secret = "Password=never-log-secret"
    token = "never-log-access-token"
    monkeypatch.setattr(secrets_service.time, "sleep", lambda delay: None)
    store = store_with_rest(
        lambda request: response(
            400,
            content_type="text/html",
            body=f"<html>{secret} {token}</html>",
            headers={
                "x-ms-request-id": "safe-request-id",
                "x-ms-keyvault-region": "centralindia",
            },
        )
    )
    with caplog.at_level("WARNING"), pytest.raises(RuntimeError):
        store.get_secret("keyvault://database-connection")
    assert secret not in caplog.text
    assert token not in caplog.text
    assert "Authorization" not in caplog.text
    assert "<html>" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    assert all(record.key_vault_http_status == 400 for record in caplog.records)
    assert all(record.key_vault_request_id == "safe-request-id" for record in caplog.records)
    assert all(record.key_vault_region == "centralindia" for record in caplog.records)
    assert all("status=400" in record.getMessage() for record in caplog.records)
    assert all("content_type=text/html" in record.getMessage() for record in caplog.records)
    assert all("request_id=safe-request-id" in record.getMessage() for record in caplog.records)
    assert all("region=centralindia" in record.getMessage() for record in caplog.records)
    assert all("classification=upstream_non_json" in record.getMessage() for record in caplog.records)
