from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from legacydb_copilot.common import DomainError, new_id, utc_now


@dataclass(frozen=True)
class Organization:
    name: str
    id: UUID = field(default_factory=new_id)
    created_at: object = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainError("Organization name is required")


@dataclass(frozen=True)
class Workspace:
    organization_id: UUID
    name: str
    id: UUID = field(default_factory=new_id)
    created_at: object = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainError("Workspace name is required")


@dataclass(frozen=True)
class TenantResource:
    organization_id: UUID
    workspace_id: UUID
    resource_type: str
    id: UUID = field(default_factory=new_id)


def assert_same_tenant(actor_org_id: UUID, resource: TenantResource) -> None:
    if actor_org_id != resource.organization_id:
        raise DomainError("Cross-tenant access denied")


def assert_workspace_belongs_to_org(workspace: Workspace, organization_id: UUID) -> None:
    if workspace.organization_id != organization_id:
        raise DomainError("Workspace does not belong to organization")
