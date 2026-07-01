from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from legacydb_copilot.common import DomainError, utc_now


class AuthProvider(StrEnum):
    EMAIL = "email"
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    GITHUB = "github"


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "organization_admin"
    DEVELOPER = "developer"
    DBA = "dba"
    SUPPORT_ENGINEER = "support_engineer"
    READ_ONLY = "read_only_user"
    AUDITOR = "auditor"


DEFAULT_ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.SUPER_ADMIN: {"*"},
    Role.ORG_ADMIN: {
        "users:manage",
        "workspaces:manage",
        "workspaces:read",
        "database:manage",
        "database:read",
        "documents:manage",
        "documents:read",
        "incidents:manage",
        "incidents:write",
        "incidents:read",
        "learning:feedback",
        "learning:approve",
        "learning:read",
        "billing:manage",
        "chat:use",
        "admin:read",
    },
    Role.DEVELOPER: {"documents:read", "chat:use", "incidents:write", "sql:analyze", "learning:feedback", "learning:read"},
    Role.DBA: {"database:manage", "sql:approve", "incidents:manage", "documents:read", "learning:approve", "learning:read"},
    Role.SUPPORT_ENGINEER: {"chat:use", "incidents:write", "documents:read", "learning:feedback", "learning:read"},
    Role.READ_ONLY: {"documents:read", "incidents:read", "learning:read"},
    Role.AUDITOR: {"audit:read", "incidents:read", "documents:read"},
}


REQUIRED_CONSENTS = frozenset(
    {
        "terms_of_service",
        "privacy_policy",
        "document_processing",
        "ai_verification_required",
    }
)


OPTIONAL_CONSENTS = frozenset({"marketing_emails", "product_updates"})


@dataclass(frozen=True)
class ConsentRecord:
    user_id: UUID
    accepted: frozenset[str]
    ip_address: str
    accepted_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        missing = REQUIRED_CONSENTS - self.accepted
        if missing:
            raise DomainError(f"Missing required consent: {', '.join(sorted(missing))}")
        unsupported = self.accepted - REQUIRED_CONSENTS - OPTIONAL_CONSENTS
        if unsupported:
            raise DomainError(f"Unsupported consent keys: {', '.join(sorted(unsupported))}")
        if not self.ip_address.strip():
            raise DomainError("Consent IP address is required")


def validate_password_strength(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must include an uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must include a lowercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must include a number")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Password must include a special character")
    return errors


def has_permission(role: Role, permission: str) -> bool:
    permissions = DEFAULT_ROLE_PERMISSIONS[role]
    return "*" in permissions or permission in permissions


@dataclass
class LoginAttemptPolicy:
    max_failed_attempts: int = 5
    lockout_minutes: int = 15
    failed_attempts: int = 0
    locked_until: datetime | None = None

    def record_failure(self, now: datetime | None = None) -> None:
        now = now or utc_now()
        if self.is_locked(now):
            return
        self.failed_attempts += 1
        if self.failed_attempts >= self.max_failed_attempts:
            self.locked_until = now + timedelta(minutes=self.lockout_minutes)

    def record_success(self) -> None:
        self.failed_attempts = 0
        self.locked_until = None

    def is_locked(self, now: datetime | None = None) -> bool:
        now = now or utc_now()
        return self.locked_until is not None and self.locked_until > now
