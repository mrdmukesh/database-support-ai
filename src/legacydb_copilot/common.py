from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> UUID:
    return uuid4()


class DomainError(ValueError):
    """Raised when a business rule is violated."""


@dataclass(frozen=True)
class AuditEvent:
    actor_id: UUID
    action: str
    target_type: str
    target_id: UUID
    occurred_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, str] = field(default_factory=dict)


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
