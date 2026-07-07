from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings


class SecretStore(Protocol):
    """
    Owner: Mukesh Dabi
    Purpose:
        Abstracts secret storage so production can store references instead of raw passwords/API keys.

    Input:
        Secret name/value on write, secret reference on read.

    Output:
        Stable secret reference or resolved secret value for internal connection use.

    Called by:
        Database connection create/update flows and connection-string builder.

    Flow:
        User enters secret -> SecretStore.store_secret -> app stores reference -> runtime resolves internally.

    Safety:
        API responses must expose only secret references/masked values, never raw database passwords or API keys.
    """

    def store_secret(self, *, name: str, value: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles store secret within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Investigation, reporting, verification, or knowledge workflows as needed.
        
        Where it fits in the flow:
            Application orchestration -> service function -> structured result for the next workflow step.
        
        Safety considerations:
            Secrets must be resolved internally and never exposed in API responses.
        """
        ...

    def get_secret(self, reference: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get secret within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Investigation, reporting, verification, or knowledge workflows as needed.
        
        Where it fits in the flow:
            Application orchestration -> service function -> structured result for the next workflow step.
        
        Safety considerations:
            Secrets must be resolved internally and never exposed in API responses.
        """
        ...


@dataclass
class LocalSecretStore:
    """Development store.

    Local mode intentionally returns the input value as the reference so existing
    development and tests keep working. API response schemas never expose it.
    """

    allow_raw_storage: bool = True

    def store_secret(self, *, name: str, value: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles store secret within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Investigation, reporting, verification, or knowledge workflows as needed.
        
        Where it fits in the flow:
            Application orchestration -> service function -> structured result for the next workflow step.
        
        Safety considerations:
            Secrets must be resolved internally and never exposed in API responses.
        """
        if not self.allow_raw_storage:
            raise RuntimeError("Production database secrets must be stored by reference")
        return value

    def get_secret(self, reference: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get secret within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Investigation, reporting, verification, or knowledge workflows as needed.
        
        Where it fits in the flow:
            Application orchestration -> service function -> structured result for the next workflow step.
        
        Safety considerations:
            Secrets must be resolved internally and never exposed in API responses.
        """
        return reference


class AzureKeyVaultSecretStore:
    def __init__(self, vault_url: str) -> None:
        """
        Owner: Mukesh Dabi
        Purpose:
            Internal helper for init within secrets_service.py.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Internal callers in secrets_service.py.
        
        Where it fits in the flow:
            Application orchestration -> service function -> structured result for the next workflow step.
        
        Safety considerations:
            Secrets must be resolved internally and never exposed in API responses.
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Azure Key Vault secrets require azure-identity and azure-keyvault-secrets"
            ) from exc
        self._client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())

    def store_secret(self, *, name: str, value: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles store secret within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Investigation, reporting, verification, or knowledge workflows as needed.
        
        Where it fits in the flow:
            Application orchestration -> service function -> structured result for the next workflow step.
        
        Safety considerations:
            Secrets must be resolved internally and never exposed in API responses.
        """
        secret_name = _safe_secret_name(name)
        self._client.set_secret(secret_name, value)
        return f"keyvault://{secret_name}"

    def get_secret(self, reference: str) -> str:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles get secret within the Database Support AI application flow.
        
        Input:
            Function parameters declared in the signature.
        
        Output:
            Return value declared by the type hints or route response model.
        
        How it is called:
            Investigation, reporting, verification, or knowledge workflows as needed.
        
        Where it fits in the flow:
            Application orchestration -> service function -> structured result for the next workflow step.
        
        Safety considerations:
            Secrets must be resolved internally and never exposed in API responses.
        """
        secret_name = reference.removeprefix("keyvault://")
        return self._client.get_secret(secret_name).value


def get_secret_store(settings: Settings | None = None) -> SecretStore:
    """
    Owner: Mukesh Dabi
    Purpose:
        Selects local or Azure Key Vault backed secret storage from feature flags and environment settings.

    Input:
        Optional Settings object.

    Output:
        SecretStore implementation.

    Called by:
        Database connection persistence and runtime connection-string assembly.

    Flow:
        Configuration -> SecretStore selection -> store/read secret references.

    Safety:
        Production should use Key Vault references. Local raw storage exists only for development/test compatibility.
    """

    resolved = settings or Settings.from_env()
    if resolved.feature_keyvault_secrets_enabled:
        if not resolved.azure_key_vault_url:
            raise RuntimeError("AZURE_KEY_VAULT_URL is required when Key Vault secrets are enabled")
        return AzureKeyVaultSecretStore(resolved.azure_key_vault_url)
    return LocalSecretStore(allow_raw_storage=resolved.environment != Environment.PRODUCTION)


def _safe_secret_name(name: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for safe secret name within secrets_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in secrets_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Secrets must be resolved internally and never exposed in API responses.
    """
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return f"{cleaned[:80]}-{uuid4().hex[:12]}" if cleaned else f"secret-{uuid4().hex[:12]}"
