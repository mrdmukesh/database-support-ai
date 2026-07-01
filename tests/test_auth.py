from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from legacydb_copilot.auth import (
    REQUIRED_CONSENTS,
    ConsentRecord,
    LoginAttemptPolicy,
    Role,
    has_permission,
    validate_password_strength,
)
from legacydb_copilot.common import DomainError


def test_password_strength_requires_enterprise_baseline() -> None:
    assert validate_password_strength("weak")
    assert validate_password_strength("StrongPass123!") == []


def test_required_consents_are_enforced() -> None:
    with pytest.raises(DomainError, match="Missing required consent"):
        ConsentRecord(user_id=uuid4(), accepted=frozenset(), ip_address="127.0.0.1")

    record = ConsentRecord(
        user_id=uuid4(),
        accepted=REQUIRED_CONSENTS,
        ip_address="127.0.0.1",
    )

    assert record.ip_address == "127.0.0.1"


def test_role_permissions() -> None:
    assert has_permission(Role.SUPER_ADMIN, "anything")
    assert has_permission(Role.DBA, "sql:approve")
    assert not has_permission(Role.READ_ONLY, "sql:approve")


def test_login_policy_locks_after_repeated_failures() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    policy = LoginAttemptPolicy(max_failed_attempts=2, lockout_minutes=10)

    policy.record_failure(now)
    assert not policy.is_locked(now)

    policy.record_failure(now)
    assert policy.is_locked(now + timedelta(minutes=1))

    policy.record_success()
    assert not policy.is_locked(now)
