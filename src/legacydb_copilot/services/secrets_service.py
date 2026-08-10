from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from threading import Lock
from typing import Protocol
from urllib.parse import quote
from uuid import uuid4

import httpx

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings

logger = logging.getLogger(__name__)
_KEY_VAULT_ATTEMPTS = 3
_KEY_VAULT_BACKOFF_SECONDS = 0.25
_KEY_VAULT_MAX_RETRY_DELAY_SECONDS = 5.0
_KEY_VAULT_SCOPE = "https://vault.azure.net/.default"
_KEY_VAULT_STORE_LOCK = Lock()


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
        if reference.startswith("env://"):
            env_name = reference.removeprefix("env://")
            value = os.getenv(env_name)
            if not value:
                raise RuntimeError(f"Environment secret reference {env_name} is not configured")
            return value
        if reference.startswith("env:"):
            env_name = reference.removeprefix("env:")
            value = os.getenv(env_name)
            if not value:
                raise RuntimeError(f"Environment secret reference {env_name} is not configured")
            return value
        return reference


class AzureKeyVaultSecretStore:
    def __init__(self, vault_url: str, *, use_managed_identity: bool = True) -> None:
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
            from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Azure Key Vault secrets require azure-identity and azure-keyvault-secrets"
            ) from exc
        credential = (
            ManagedIdentityCredential()
            if use_managed_identity
            else DefaultAzureCredential()
        )
        self._credential = credential
        self._client = SecretClient(vault_url=vault_url, credential=credential)
        self._vault_url = vault_url.rstrip("/")
        self._use_rest_for_reads = use_managed_identity
        self._http_client = httpx.Client(timeout=10.0)

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
        if self._use_rest_for_reads:
            return self._get_secret_with_rest(reference)
        secret_name = reference.removeprefix("keyvault://")
        for attempt in range(1, _KEY_VAULT_ATTEMPTS + 1):
            try:
                return self._client.get_secret(secret_name).value
            except Exception as exc:
                transient = _is_transient_key_vault_error(exc)
                _log_key_vault_failure(exc, attempt=attempt, transient=transient)
                if attempt == _KEY_VAULT_ATTEMPTS or not transient:
                    raise RuntimeError("Secure secret retrieval failed") from exc
                time.sleep(_KEY_VAULT_BACKOFF_SECONDS * (2 ** (attempt - 1)))
        raise RuntimeError("Secure secret retrieval failed")  # pragma: no cover

    def _get_secret_with_rest(self, reference: str) -> str:
        secret_name = reference.removeprefix("keyvault://")
        secret_url = f"{self._vault_url}/secrets/{quote(secret_name, safe='')}"
        for attempt in range(1, _KEY_VAULT_ATTEMPTS + 1):
            response = None
            try:
                access_token = self._credential.get_token(_KEY_VAULT_SCOPE)
                response = self._http_client.get(
                    secret_url,
                    params={"api-version": "7.4"},
                    headers={"Authorization": f"Bearer {access_token.token}"},
                )
                classification = _classify_key_vault_response(response)
                if classification == "success_json":
                    payload = response.json()
                    if not isinstance(payload, dict) or not isinstance(payload.get("value"), str):
                        raise _KeyVaultProtocolError("missing_secret_value", response=response)
                    return payload["value"]
                raise _KeyVaultProtocolError(classification, response=response)
            except Exception as exc:
                classification = getattr(exc, "classification", "transport_or_token_error")
                transient = _is_transient_rest_failure(exc, response, classification)
                _log_key_vault_failure(
                    exc,
                    attempt=attempt,
                    transient=transient,
                    response=response,
                    classification=classification,
                )
                if attempt == _KEY_VAULT_ATTEMPTS or not transient:
                    raise RuntimeError("Secure secret retrieval failed") from exc
                time.sleep(_key_vault_retry_delay(response, attempt))
        raise RuntimeError("Secure secret retrieval failed")  # pragma: no cover


class _KeyVaultProtocolError(Exception):
    def __init__(self, classification: str, *, response: httpx.Response) -> None:
        super().__init__(classification)
        self.classification = classification
        self.response = response


def _classify_key_vault_response(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").lower()
    is_json = "application/json" in content_type or "+json" in content_type
    if response.status_code == 200:
        if not is_json:
            return "success_non_json"
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return "success_malformed_json"
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), str):
            return "success_missing_secret_value"
        return "success_json"
    if response.status_code in {401, 403}:
        return "authorization_error"
    if response.status_code in {408, 429, 500, 502, 503, 504}:
        return "transient_http_error"
    if not is_json:
        return "upstream_non_json"
    return "non_retryable_http_error"


def _is_transient_rest_failure(
    exc: Exception,
    response: httpx.Response | None,
    classification: str,
) -> bool:
    if isinstance(exc, (httpx.TransportError, TimeoutError)):
        return True
    if response is None:
        return _is_transient_key_vault_error(exc) or type(exc).__name__ in {
            "ServiceRequestError",
            "ServiceResponseError",
        }
    return classification in {
        "success_non_json",
        "success_malformed_json",
        "success_missing_secret_value",
        "transient_http_error",
        "upstream_non_json",
    }


def _key_vault_retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    delay = 0.0
            if delay > 0:
                return min(delay, _KEY_VAULT_MAX_RETRY_DELAY_SECONDS)
    return min(
        _KEY_VAULT_BACKOFF_SECONDS * (2 ** (attempt - 1)),
        _KEY_VAULT_MAX_RETRY_DELAY_SECONDS,
    )


def _is_transient_key_vault_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 429} or (isinstance(status_code, int) and status_code >= 500):
        return True
    if status_code != 400:
        return False
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("content-type", headers.get("Content-Type", ""))).lower()
    return "text/html" in content_type


def _log_key_vault_failure(
    exc: Exception,
    *,
    attempt: int,
    transient: bool,
    response=None,
    classification: str = "sdk_error",
) -> None:
    if response is None:
        response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    status_code = getattr(
        exc,
        "status_code",
        getattr(response, "status_code", None),
    )
    content_type = headers.get("content-type", headers.get("Content-Type"))
    request_id = headers.get("x-ms-request-id")
    region = headers.get("x-ms-keyvault-region")
    exception_class = type(exc).__name__
    timestamp = datetime.now(UTC).isoformat()
    logger.warning(
        (
            "key_vault_secret_read_failed timestamp=%s attempt=%s status=%s "
            "content_type=%s request_id=%s region=%s exception_class=%s "
            "classification=%s transient=%s"
        ),
        timestamp,
        attempt,
        status_code,
        content_type,
        request_id,
        region,
        exception_class,
        classification,
        transient,
        extra={
            "key_vault_http_status": status_code,
            "key_vault_content_type": content_type,
            "key_vault_request_id": request_id,
            "key_vault_region": region,
            "key_vault_exception_class": exception_class,
            "key_vault_retry_attempt": attempt,
            "key_vault_transient": transient,
            "key_vault_response_classification": classification,
            "key_vault_failure_timestamp": timestamp,
        },
    )


@lru_cache(maxsize=8)
def _cached_azure_secret_store(
    vault_url: str,
    use_managed_identity: bool,
) -> AzureKeyVaultSecretStore:
    return AzureKeyVaultSecretStore(
        vault_url,
        use_managed_identity=use_managed_identity,
    )


def _shared_azure_secret_store(
    vault_url: str,
    use_managed_identity: bool,
) -> AzureKeyVaultSecretStore:
    # lru_cache may invoke its wrapped function more than once for concurrent
    # first-time misses. Serialize lookup plus construction so one credential
    # and client exist for each process-local configuration key.
    with _KEY_VAULT_STORE_LOCK:
        return _cached_azure_secret_store(vault_url, use_managed_identity)


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
        return _shared_azure_secret_store(
            resolved.azure_key_vault_url,
            resolved.environment == Environment.PRODUCTION,
        )
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
