from types import SimpleNamespace

import pytest

from legacydb_copilot.services.secrets_service import AzureKeyVaultSecretStore


class KeyVaultFailure(Exception):
    def __init__(self, status_code: int, content_type: str = "application/json") -> None:
        super().__init__("secret lookup failed")
        self.status_code = status_code
        self.response = SimpleNamespace(headers={"content-type": content_type})


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
