from __future__ import annotations

import base64
import hmac
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from legacydb_copilot.common import DomainError


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        int(iterations),
    )
    return secrets.compare_digest(digest.hex(), expected)


def create_access_token(
    *,
    user_id: str,
    organization_id: str,
    role: str,
    secret: str,
    expires_minutes: int,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "organization_id": organization_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
        signing_input = f"{header_part}.{payload_part}"
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual_signature = _base64url_decode(signature_part)
        if not secrets.compare_digest(actual_signature, expected_signature):
            raise DomainError("Invalid token signature")

        header = json.loads(_base64url_decode(header_part))
        if header.get("alg") != "HS256":
            raise DomainError("Unsupported token algorithm")

        payload = json.loads(_base64url_decode(payload_part))
        expires_at = int(payload["exp"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise DomainError("Invalid access token") from exc

    if expires_at <= int(datetime.now(UTC).timestamp()):
        raise DomainError("Access token expired")
    return payload
