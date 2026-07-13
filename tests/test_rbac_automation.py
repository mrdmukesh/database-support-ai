"""Automated regression coverage for the application's default RBAC contract."""

from __future__ import annotations

import pytest

from legacydb_copilot.auth import DEFAULT_ROLE_PERMISSIONS, Role, has_permission


EXPECTED_PERMISSIONS: dict[Role, set[str]] = {
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
    Role.DEVELOPER: {
        "documents:read",
        "chat:use",
        "incidents:write",
        "sql:analyze",
        "learning:feedback",
        "learning:read",
    },
    Role.DBA: {
        "database:manage",
        "database:read",
        "sql:approve",
        "incidents:manage",
        "documents:read",
        "learning:approve",
        "learning:read",
    },
    Role.SUPPORT_ENGINEER: {
        "chat:use",
        "incidents:write",
        "documents:read",
        "learning:feedback",
        "learning:read",
    },
    Role.READ_ONLY: {"documents:read", "incidents:read", "learning:read"},
    Role.AUDITOR: {"audit:read", "incidents:read", "documents:read"},
}

SENSITIVE_PERMISSIONS = (
    "users:manage",
    "workspaces:manage",
    "database:manage",
    "documents:manage",
    "incidents:manage",
    "learning:feedback",
    "learning:approve",
    "billing:manage",
    "sql:approve",
    "audit:read",
)


def test_default_role_permission_sets_match_the_reviewed_contract() -> None:
    """Any permission grant or removal must be an explicit, reviewed test change."""
    assert set(DEFAULT_ROLE_PERMISSIONS) == set(Role)
    assert DEFAULT_ROLE_PERMISSIONS == EXPECTED_PERMISSIONS


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", SENSITIVE_PERMISSIONS)
def test_sensitive_permission_decisions_match_the_reviewed_matrix(
    role: Role, permission: str
) -> None:
    expected = role is Role.SUPER_ADMIN or permission in EXPECTED_PERMISSIONS[role]
    assert has_permission(role, permission) is expected


def test_feedback_submission_and_approval_have_intentional_role_separation() -> None:
    submitters = {
        role for role in Role if has_permission(role, "learning:feedback")
    }
    approvers = {
        role for role in Role if has_permission(role, "learning:approve")
    }

    assert submitters == {
        Role.SUPER_ADMIN,
        Role.ORG_ADMIN,
        Role.DEVELOPER,
        Role.SUPPORT_ENGINEER,
    }
    assert approvers == {Role.SUPER_ADMIN, Role.ORG_ADMIN, Role.DBA}
    assert not has_permission(Role.DEVELOPER, "learning:approve")
    assert not has_permission(Role.SUPPORT_ENGINEER, "learning:approve")
    assert not has_permission(Role.DBA, "learning:feedback")


@pytest.mark.parametrize("role", [Role.READ_ONLY, Role.AUDITOR])
def test_observer_roles_cannot_mutate_protected_resources(role: Role) -> None:
    mutation_permissions = {
        "users:manage",
        "workspaces:manage",
        "database:manage",
        "documents:manage",
        "incidents:manage",
        "incidents:write",
        "learning:feedback",
        "learning:approve",
        "billing:manage",
        "sql:approve",
    }
    assert all(not has_permission(role, permission) for permission in mutation_permissions)


@pytest.mark.parametrize("role", [role for role in Role if role is not Role.SUPER_ADMIN])
def test_unknown_permissions_are_denied_for_non_super_admin_roles(role: Role) -> None:
    assert not has_permission(role, "unknown:future-capability")


def test_super_admin_wildcard_allows_registered_and_future_permissions() -> None:
    assert has_permission(Role.SUPER_ADMIN, "learning:approve")
    assert has_permission(Role.SUPER_ADMIN, "unknown:future-capability")
