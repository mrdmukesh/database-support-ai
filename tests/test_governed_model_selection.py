from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role, has_permission
from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    LLMModelCatalogModel,
    LLMModelPolicyModel,
    LLMModelRoleEntitlementModel,
    LLMModelSelectionAuditModel,
    LLMModelUserEntitlementModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.governed_model_selection import (
    GovernedModelSelectionService,
    ModelSelectionAuthorizationError,
    ModelSelectionRequest,
)


@pytest.fixture
def governed_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = OrganizationModel(name="Governed", slug="governed")
        db.add(org)
        db.flush()
        workspace = WorkspaceModel(organization_id=org.id, name="Production", slug="production")
        user = UserModel(
            organization_id=org.id,
            email="developer@example.com",
            password_hash="hash",
            full_name="Developer",
            role=Role.DEVELOPER.value,
            is_active=True,
        )
        db.add_all([workspace, user])
        db.flush()
        fast = LLMModelCatalogModel(
            organization_id=org.id,
            display_name="Fast",
            provider="openai",
            provider_model_id="configured-fast",
            model_category="fast",
            automatic_eligible=True,
            cost_tier="low",
            latency_tier="low",
        )
        deep = LLMModelCatalogModel(
            organization_id=org.id,
            display_name="Deep Analysis",
            provider="openai",
            provider_model_id="configured-deep",
            model_category="deep_analysis",
            automatic_eligible=True,
            premium=True,
            cost_tier="premium",
            latency_tier="high",
        )
        disabled = LLMModelCatalogModel(
            organization_id=org.id,
            display_name="Disabled",
            provider="openai",
            provider_model_id="configured-disabled",
            enabled=False,
        )
        db.add_all([fast, deep, disabled])
        db.flush()
        policy = LLMModelPolicyModel(
            organization_id=org.id,
            user_selection_enabled=True,
            automatic_mode_enabled=True,
            global_default_model_id=fast.id,
            automatic_candidate_ids_json=f'["{fast.id}","{deep.id}"]',
            fallback_model_id=fast.id,
            fallback_enabled=False,
            require_premium_approval=True,
            allowed_environments_json='["production"]',
        )
        db.add(policy)
        db.commit()
        yield db, org, workspace, user, fast, deep, disabled, policy


def settings(**updates) -> Settings:
    return replace(
        Settings(
            environment=Environment.TESTING,
            model_selection_enabled=True,
            model_selection_automatic_enabled=True,
        ),
        **updates,
    )


def resolve(db, user, workspace, request, question="Routine issue", **setting_updates):
    return GovernedModelSelectionService(db, settings(**setting_updates)).resolve(
        user=user,
        workspace_id=workspace.id,
        environment="production",
        request=request,
        question=question,
    )


def test_feature_disabled_preserves_existing_model_and_old_client(governed_db):
    db, _org, workspace, user, *_ = governed_db
    resolved = GovernedModelSelectionService(
        db, settings(model_selection_enabled=False, llm_reasoning_model="existing-model")
    ).resolve(
        user=user,
        workspace_id=workspace.id,
        environment="production",
        request=ModelSelectionRequest(),
        question="Question",
    )
    assert resolved.provider_model_id == "existing-model"
    assert resolved.selection_source == "administrator_default"


def test_browser_cannot_submit_arbitrary_provider_model(governed_db):
    db, _org, workspace, user, *_ = governed_db
    with pytest.raises(ModelSelectionAuthorizationError, match="not permitted"):
        resolve(
            db,
            user,
            workspace,
            ModelSelectionRequest(mode="model", catalog_model_id="gpt-arbitrary"),
        )


def test_disabled_model_is_rejected(governed_db):
    db, _org, workspace, user, _fast, _deep, disabled, _policy = governed_db
    with pytest.raises(ModelSelectionAuthorizationError):
        resolve(
            db, user, workspace, ModelSelectionRequest(mode="model", catalog_model_id=disabled.id)
        )


def test_role_entitlement_is_enforced(governed_db):
    db, org, workspace, user, fast, *_ = governed_db
    db.add(
        LLMModelRoleEntitlementModel(
            organization_id=org.id, model_id=fast.id, role=Role.DBA.value, allowed=True
        )
    )
    db.commit()
    with pytest.raises(ModelSelectionAuthorizationError):
        resolve(db, user, workspace, ModelSelectionRequest(mode="model", catalog_model_id=fast.id))


def test_premium_user_approval_and_expiration(governed_db):
    db, org, workspace, user, _fast, deep, *_ = governed_db
    request = ModelSelectionRequest(mode="model", catalog_model_id=deep.id)
    with pytest.raises(ModelSelectionAuthorizationError):
        resolve(db, user, workspace, request)
    db.add(
        LLMModelUserEntitlementModel(
            organization_id=org.id,
            model_id=deep.id,
            user_id=user.id,
            allowed=True,
            approval_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()
    assert resolve(db, user, workspace, request).provider_model_id == "configured-deep"
    row = db.query(LLMModelUserEntitlementModel).one()
    row.approval_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    with pytest.raises(ModelSelectionAuthorizationError):
        resolve(db, user, workspace, request)


def test_fallback_is_explicitly_double_gated(governed_db):
    db, _org, workspace, user, _fast, _deep, disabled, policy = governed_db
    request = ModelSelectionRequest(mode="model", catalog_model_id=disabled.id)
    policy.fallback_enabled = True
    db.commit()
    with pytest.raises(ModelSelectionAuthorizationError):
        resolve(db, user, workspace, request, model_selection_fallback_enabled=False)
    resolved = resolve(db, user, workspace, request, model_selection_fallback_enabled=True)
    assert resolved.selection_source == "fallback"
    assert resolved.fallback_reason == "requested_model_not_authorized_or_available"


def test_automatic_filters_candidates_and_selects_deterministically(governed_db):
    db, org, workspace, user, fast, deep, *_ = governed_db
    db.add(
        LLMModelUserEntitlementModel(
            organization_id=org.id,
            model_id=deep.id,
            user_id=user.id,
            allowed=True,
            approval_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()
    routine = resolve(db, user, workspace, ModelSelectionRequest(mode="automatic"))
    complex_result = resolve(
        db,
        user,
        workspace,
        ModelSelectionRequest(mode="automatic"),
        question=(
            "Trace all related records across procedures and determine the root cause "
            "of this multi-step contradiction."
        ),
    )
    assert routine.effective_catalog_model_id == fast.id
    assert complex_result.effective_catalog_model_id == deep.id
    assert set(complex_result.candidate_model_ids) == {fast.id, deep.id}
    assert complex_result.routing_factors["complex"] is True


def test_selection_decision_is_audited_without_secrets(governed_db):
    db, _org, workspace, user, fast, *_ = governed_db
    resolved = resolve(
        db, user, workspace, ModelSelectionRequest(mode="model", catalog_model_id=fast.id)
    )
    row = db.get(LLMModelSelectionAuditModel, resolved.audit_id)
    assert row is not None
    assert row.requested_catalog_model_id == fast.id
    assert row.effective_provider_model_id == "configured-fast"
    assert "api_key" not in row.model_snapshot_json


def test_model_management_permission_is_admin_only():
    assert has_permission(Role.SUPER_ADMIN, "models:manage")
    assert has_permission(Role.ORG_ADMIN, "models:manage")
    assert not has_permission(Role.DEVELOPER, "models:manage")


def test_workspace_entitlement_is_part_of_intersection(governed_db):
    from legacydb_copilot.db.models import LLMModelWorkspaceEntitlementModel

    db, org, workspace, user, fast, *_ = governed_db
    other = WorkspaceModel(organization_id=org.id, name="Other", slug="other")
    db.add(other)
    db.flush()
    db.add(
        LLMModelWorkspaceEntitlementModel(
            organization_id=org.id, model_id=fast.id, workspace_id=other.id, allowed=True
        )
    )
    db.commit()
    with pytest.raises(ModelSelectionAuthorizationError):
        resolve(db, user, workspace, ModelSelectionRequest(mode="model", catalog_model_id=fast.id))


def test_resolved_configuration_is_immutable_and_reaches_provider_settings(governed_db):
    db, _org, workspace, user, fast, *_ = governed_db
    resolved = resolve(
        db, user, workspace, ModelSelectionRequest(mode="model", catalog_model_id=fast.id)
    )
    invocation_settings = resolved.apply_to_settings(settings())
    assert invocation_settings.selected_reasoning_model == "configured-fast"
    assert invocation_settings.llm_provider == "openai"
    assert invocation_settings.llm_reasoning_effort == fast.default_reasoning_effort
