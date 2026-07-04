from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings


class SecretStore(Protocol):
    def store_secret(self, *, name: str, value: str) -> str:
        ...

    def get_secret(self, reference: str) -> str:
        ...


@dataclass
class LocalSecretStore:
    """Development store.

    Local mode intentionally returns the input value as the reference so existing
    development and tests keep working. API response schemas never expose it.
    """

    allow_raw_storage: bool = True

    def store_secret(self, *, name: str, value: str) -> str:
        if not self.allow_raw_storage:
            raise RuntimeError("Production database secrets must be stored by reference")
        return value

    def get_secret(self, reference: str) -> str:
        return reference


class AzureKeyVaultSecretStore:
    def __init__(self, vault_url: str) -> None:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Azure Key Vault secrets require azure-identity and azure-keyvault-secrets"
            ) from exc
        self._client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())

    def store_secret(self, *, name: str, value: str) -> str:
        secret_name = _safe_secret_name(name)
        self._client.set_secret(secret_name, value)
        return f"keyvault://{secret_name}"

    def get_secret(self, reference: str) -> str:
        secret_name = reference.removeprefix("keyvault://")
        return self._client.get_secret(secret_name).value


def get_secret_store(settings: Settings | None = None) -> SecretStore:
    resolved = settings or Settings.from_env()
    if resolved.feature_keyvault_secrets_enabled:
        if not resolved.azure_key_vault_url:
            raise RuntimeError("AZURE_KEY_VAULT_URL is required when Key Vault secrets are enabled")
        return AzureKeyVaultSecretStore(resolved.azure_key_vault_url)
    return LocalSecretStore(allow_raw_storage=resolved.environment != Environment.PRODUCTION)


def _safe_secret_name(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return f"{cleaned[:80]}-{uuid4().hex[:12]}" if cleaned else f"secret-{uuid4().hex[:12]}"
