from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "access_token",
    "api_key",
    "apikey",
    "connection_string",
    "database_url",
}
PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)((?:password|pwd|secret|token|api[_-]?key)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(://[^:/\s]+:)[^@\s]+(@)"),
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        result = value
        for pattern in PATTERNS:

            def replacement(match: re.Match[str]) -> str:
                groups = match.groups()
                prefix = groups[0] if groups else ""
                suffix = groups[1] if len(groups) > 1 and groups[1] == "@" else ""
                return prefix + "[REDACTED]" + suffix

            result = pattern.sub(replacement, result)
        return result
    return value
