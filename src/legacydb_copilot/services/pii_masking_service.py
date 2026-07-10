from __future__ import annotations

import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
SENSITIVE_KEY_RE = re.compile(
    r"(name|email|phone|mobile|insurance|account|ssn|aadhaar|member|policy|patient)",
    re.I,
)
ACCOUNT_LIKE_RE = re.compile(r"\b(?:ACCT|ACC|INS|POL|SSN|MRN|PAT)(?:[-_][A-Z0-9]{4,}|\d{4,})\b", re.I)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|private[_-]?key|token|connection[_-]?string)\b\s*[:=]\s*['\"]?[^'\"\s,;}{]+"
)
CONNECTION_STRING_RE = re.compile(
    r"(?i)\b(?:postgresql|postgres|mysql(?:\+pymysql)?|mssql(?:\+pyodbc)?|sqlserver|oracle|sqlite)://[^\s\"'<>]+"
)
AZURE_STORAGE_CONNECTION_RE = re.compile(
    r"(?i)\b(DefaultEndpointsProtocol|AccountName|AccountKey|SharedAccessSignature|BlobEndpoint|QueueEndpoint|TableEndpoint|FileEndpoint)=[^;\s]+"
)
BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")
ROLE_NAME_RE = re.compile(
    r"\b(patient|customer|member|doctor|student|employee)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b",
    re.I,
)


def mask_secrets_text(value: str) -> str:
    masked = CONNECTION_STRING_RE.sub("[MASKED_CONNECTION_STRING]", value)
    masked = AZURE_STORAGE_CONNECTION_RE.sub(lambda match: f"{match.group(1)}=[MASKED_SECRET]", masked)
    masked = BEARER_TOKEN_RE.sub("Bearer [MASKED_TOKEN]", masked)
    masked = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[MASKED_SECRET]", masked)
    return masked


def mask_sensitive_value(key: str, value: Any) -> Any:
    """
    Owner: Mukesh Dabi
    Purpose:
        Masks likely PII values before evidence is sent to an LLM.

    Input:
        Field key/name and raw value.

    Output:
        Masked value for names, email, phone, insurance/account identifiers, and similar sensitive data.

    How it is called:
        Internal callers in pii_masking_service.py and LLM payload preparation.

    Where it fits in the flow:
        Safe SQL evidence -> PII masking -> optional OpenAI reasoning payload.

    Safety considerations:
        This must not alter SQL evidence collection or stored evidence; it only masks the outbound LLM payload.
    """
    if value is None:
        return value
    if not isinstance(value, str):
        value = str(value) if SENSITIVE_KEY_RE.search(key or "") else value
    if not isinstance(value, str):
        return value
    value = mask_secrets_text(value)
    if re.search(r"(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|private[_-]?key|token|connection[_-]?string)", key or "", re.I):
        return "[MASKED_SECRET]" if value.strip() else value
    if EMAIL_RE.search(value):
        return EMAIL_RE.sub("[MASKED_EMAIL]", value)
    if PHONE_RE.search(value):
        return PHONE_RE.sub("[MASKED_PHONE]", value)
    if ACCOUNT_LIKE_RE.search(value):
        return ACCOUNT_LIKE_RE.sub("[MASKED_IDENTIFIER]", value)
    if ROLE_NAME_RE.search(value):
        return ROLE_NAME_RE.sub(lambda match: f"{match.group(1)} [MASKED_NAME]", value)
    if SENSITIVE_KEY_RE.search(key or ""):
        if value.strip():
            return "[MASKED_PII]"
    return value


def mask_llm_payload(value: Any, key: str = "") -> Any:
    """
    Owner: Mukesh Dabi
    Purpose:
        Recursively masks likely PII from the evidence package before optional LLM reasoning.

    Input:
        Any nested payload value and its field key.

    Output:
        Payload with sensitive values masked while preserving structure.

    How it is called:
        LLM reasoning service immediately before calling OpenAI.

    Where it fits in the flow:
        Evidence package construction -> PII masking -> OpenAI request.

    Safety considerations:
        The deterministic engine keeps original evidence; only the LLM-bound copy is masked.
    """
    if isinstance(value, dict):
        return {item_key: mask_llm_payload(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [mask_llm_payload(item, key) for item in value]
    return mask_sensitive_value(key, value)


def sanitize_ai_trace(trace: Any) -> Any:
    """
    Masks secrets, connection strings, credentials, tokens, and PII from persisted/downloaded AI traces.
    """
    return mask_llm_payload(trace)
