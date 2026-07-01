from uuid import uuid4

import pytest

from legacydb_copilot.common import DomainError
from legacydb_copilot.tenancy import (
    Organization,
    TenantResource,
    Workspace,
    assert_same_tenant,
    assert_workspace_belongs_to_org,
)


def test_workspace_must_belong_to_organization() -> None:
    org = Organization("Acme")
    workspace = Workspace(organization_id=org.id, name="Finance")

    assert_workspace_belongs_to_org(workspace, org.id)

    with pytest.raises(DomainError, match="Workspace does not belong"):
        assert_workspace_belongs_to_org(workspace, uuid4())


def test_cross_tenant_access_is_denied() -> None:
    org = Organization("Acme")
    resource = TenantResource(
        organization_id=org.id,
        workspace_id=uuid4(),
        resource_type="document",
    )

    assert_same_tenant(org.id, resource)

    with pytest.raises(DomainError, match="Cross-tenant access denied"):
        assert_same_tenant(uuid4(), resource)
