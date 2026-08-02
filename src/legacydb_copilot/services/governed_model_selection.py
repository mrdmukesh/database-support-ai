from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import (
    LLMModelCatalogModel,
    LLMModelPolicyModel,
    LLMModelRoleEntitlementModel,
    LLMModelSelectionAuditModel,
    LLMModelUserEntitlementModel,
    LLMModelWorkspaceEntitlementModel,
    UserModel,
)

MODEL_MODES = {"automatic", "fast", "deep_analysis", "model"}
AVAILABLE_STATUSES = {"available", "preview"}
EFFORT_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}
COST_ORDER = {"low": 0, "standard": 1, "premium": 2}


class ModelSelectionError(ValueError):
    pass


class ModelSelectionAuthorizationError(ModelSelectionError):
    pass


@dataclass(frozen=True)
class ModelSelectionRequest:
    mode: str = ""
    catalog_model_id: str = ""


@dataclass(frozen=True)
class ResolvedModelSelection:
    requested_mode: str
    requested_catalog_model_id: str
    effective_catalog_model_id: str
    provider: str
    provider_model_id: str
    reasoning_effort: str
    selection_source: str
    policy_decision: str
    policy_decision_reason: str
    entitlement_source: str
    fallback_reason: str
    candidate_model_ids: tuple[str, ...]
    routing_factors: dict[str, Any]
    model_snapshot: dict[str, Any]
    configuration_version: int
    requested_at: datetime
    timeout_seconds: float = 60.0
    max_output_tokens: int = 4000
    audit_id: str = ""

    def apply_to_settings(self, settings: Settings) -> Settings:
        return replace(
            settings,
            llm_provider=self.provider,
            llm_model=self.provider_model_id,
            llm_requested_model=self.provider_model_id,
            llm_reasoning_model=self.provider_model_id,
            llm_reasoning_effort=self.reasoning_effort,
            llm_provider_timeout_seconds=self.timeout_seconds,
            llm_request_timeout_seconds=self.timeout_seconds,
            llm_max_output_tokens=self.max_output_tokens,
        )


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _active_approval(row: LLMModelUserEntitlementModel, now: datetime) -> bool:
    starts = row.approval_starts_at
    expires = row.approval_expires_at
    if starts is not None and starts.tzinfo is None:
        starts = starts.replace(tzinfo=UTC)
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return bool(
        row.allowed and (starts is None or starts <= now) and (expires is None or expires > now)
    )


def _catalog_snapshot(model: LLMModelCatalogModel) -> dict[str, Any]:
    return {
        "id": model.id,
        "display_name": model.display_name,
        "provider": model.provider,
        "provider_model_id": model.provider_model_id,
        "model_category": model.model_category,
        "default_reasoning_effort": model.default_reasoning_effort,
        "maximum_reasoning_effort": model.maximum_reasoning_effort,
        "context_limit": model.context_limit,
        "cost_tier": model.cost_tier,
        "latency_tier": model.latency_tier,
        "availability_status": model.availability_status,
        "configuration_version": model.configuration_version,
    }


class GovernedModelSelectionService:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or Settings.from_env()

    def policy_for(self, organization_id: str) -> LLMModelPolicyModel | None:
        return (
            self.db.query(LLMModelPolicyModel)
            .filter(LLMModelPolicyModel.organization_id == organization_id)
            .one_or_none()
        )

    def allowed_models(
        self,
        *,
        user: UserModel,
        workspace_id: str,
        environment: str,
    ) -> list[tuple[LLMModelCatalogModel, str]]:
        now = datetime.now(UTC)
        policy = self.policy_for(user.organization_id)
        if policy is None:
            return []
        allowed_environments = {
            item.casefold() for item in _json_list(policy.allowed_environments_json)
        }
        if allowed_environments and environment.casefold() not in allowed_environments:
            return []
        selection_roles = set(_json_list(policy.selection_roles_json))
        if selection_roles and user.role not in selection_roles:
            return []

        models = (
            self.db.query(LLMModelCatalogModel)
            .filter(
                LLMModelCatalogModel.organization_id == user.organization_id,
                LLMModelCatalogModel.enabled.is_(True),
                LLMModelCatalogModel.availability_status.in_(AVAILABLE_STATUSES),
            )
            .order_by(LLMModelCatalogModel.sort_order, LLMModelCatalogModel.display_name)
            .all()
        )
        result: list[tuple[LLMModelCatalogModel, str]] = []
        for model in models:
            if model.provider.casefold() != self.settings.llm_provider.casefold():
                continue
            if COST_ORDER.get(model.cost_tier, 1) > COST_ORDER.get(policy.cost_ceiling_tier, 2):
                continue
            if model.retirement_date:
                retirement = model.retirement_date
                if retirement.tzinfo is None:
                    retirement = retirement.replace(tzinfo=UTC)
                if retirement <= now:
                    continue
            role_rows = (
                self.db.query(LLMModelRoleEntitlementModel)
                .filter_by(organization_id=user.organization_id, model_id=model.id)
                .all()
            )
            if role_rows and not any(row.role == user.role and row.allowed for row in role_rows):
                continue
            workspace_rows = (
                self.db.query(LLMModelWorkspaceEntitlementModel)
                .filter_by(organization_id=user.organization_id, model_id=model.id)
                .all()
            )
            if workspace_rows and not any(
                row.workspace_id == workspace_id and row.allowed for row in workspace_rows
            ):
                continue
            user_row = (
                self.db.query(LLMModelUserEntitlementModel)
                .filter_by(organization_id=user.organization_id, model_id=model.id, user_id=user.id)
                .one_or_none()
            )
            if user_row is not None and not _active_approval(user_row, now):
                continue
            if (
                model.premium
                and policy.require_premium_approval
                and (user_row is None or not _active_approval(user_row, now))
            ):
                continue
            sources = ["global"]
            if role_rows:
                sources.append(f"role:{user.role}")
            if workspace_rows:
                sources.append(f"workspace:{workspace_id}")
            if user_row is not None:
                sources.append(f"user:{user.id}")
            result.append((model, ",".join(sources)))
        return result

    def available_response(
        self, *, user: UserModel, workspace_id: str, environment: str
    ) -> dict[str, Any]:
        policy = self.policy_for(user.organization_id)
        enabled = bool(
            self.settings.model_selection_enabled and policy and policy.user_selection_enabled
        )
        allowed = (
            self.allowed_models(user=user, workspace_id=workspace_id, environment=environment)
            if enabled
            else []
        )
        options: list[dict[str, Any]] = []
        if (
            enabled
            and policy
            and self.settings.model_selection_automatic_enabled
            and policy.automatic_mode_enabled
        ):
            options.append(
                {
                    "value": "automatic",
                    "mode": "automatic",
                    "display_name": "Automatic",
                    "description": (
                        "Recommended — application selects from "
                        "administrator-approved models."
                    ),
                    "latency_tier": "policy",
                    "cost_tier": "policy",
                    "recommended_usage": "Recommended default",
                    "approval_required": False,
                    "disabled": False,
                    "disabled_reason": "",
                }
            )
        for model, _source in allowed:
            options.append(
                {
                    "value": model.id,
                    "mode": model.model_category
                    if model.model_category in {"fast", "deep_analysis"}
                    else "model",
                    "display_name": model.display_name,
                    "description": model.description,
                    "latency_tier": model.latency_tier,
                    "cost_tier": model.cost_tier,
                    "recommended_usage": model.recommended_usage,
                    "approval_required": bool(
                        model.premium and policy and policy.require_premium_approval
                    ),
                    "disabled": False,
                    "disabled_reason": "",
                }
            )
        return {
            "selection_enabled": enabled,
            "automatic_enabled": bool(enabled and policy and policy.automatic_mode_enabled),
            "default_value": "automatic"
            if enabled and policy and policy.automatic_mode_enabled
            else (policy.global_default_model_id if enabled and policy else ""),
            "policy_version": str(policy.configuration_version if policy else 0),
            "options": options,
        }

    def resolve(
        self,
        *,
        user: UserModel,
        workspace_id: str,
        environment: str,
        request: ModelSelectionRequest,
        question: str,
    ) -> ResolvedModelSelection:
        now = datetime.now(UTC)
        policy = self.policy_for(user.organization_id)
        feature_enabled = bool(
            self.settings.model_selection_enabled and policy and policy.user_selection_enabled
        )
        if not feature_enabled:
            if request.mode or request.catalog_model_id:
                raise ModelSelectionAuthorizationError("User model selection is disabled.")
            resolved = ResolvedModelSelection(
                requested_mode="",
                requested_catalog_model_id="",
                effective_catalog_model_id="",
                provider=self.settings.llm_provider,
                provider_model_id=self.settings.selected_reasoning_model,
                reasoning_effort=self.settings.llm_reasoning_effort,
                selection_source="administrator_default",
                policy_decision="allowed",
                policy_decision_reason="feature_disabled_existing_configuration",
                entitlement_source="existing_configuration",
                fallback_reason="",
                candidate_model_ids=(),
                routing_factors={},
                model_snapshot={
                    "provider": self.settings.llm_provider,
                    "provider_model_id": self.settings.selected_reasoning_model,
                },
                configuration_version=0,
                requested_at=now,
            )
            return self._audit(user, workspace_id, resolved)

        assert policy is not None
        allowed = self.allowed_models(user=user, workspace_id=workspace_id, environment=environment)
        allowed_by_id = {model.id: (model, source) for model, source in allowed}
        requested_mode = (request.mode or "").strip().casefold()
        requested_id = request.catalog_model_id.strip()
        if requested_mode and requested_mode not in MODEL_MODES:
            raise ModelSelectionError("Unsupported model selection mode.")

        candidates: list[LLMModelCatalogModel] = []
        factors: dict[str, Any] = {}
        source = "user"
        if requested_mode == "automatic":
            if not (
                self.settings.model_selection_automatic_enabled and policy.automatic_mode_enabled
            ):
                raise ModelSelectionAuthorizationError("Automatic model selection is disabled.")
            configured = set(_json_list(policy.automatic_candidate_ids_json))
            candidates = [
                model
                for model, _ in allowed
                if model.automatic_eligible and (not configured or model.id in configured)
            ]
            if not candidates:
                raise ModelSelectionAuthorizationError(
                    "No authorized Automatic-mode model is available."
                )
            factors = self._routing_factors(question)
            preferred_category = (
                "fast"
                if policy.latency_preference == "low"
                else "deep_analysis"
                if factors["complex"]
                else "fast"
            )
            selected = next(
                (item for item in candidates if item.model_category == preferred_category),
                candidates[0],
            )
            source = "automatic_router"
            reason = f"automatic_{preferred_category}_policy"
        else:
            selected_id = (
                requested_id
                or policy.global_default_model_id
                or self.settings.model_selection_default_catalog_model_id
            )
            source = "user" if requested_id else "administrator_default"
            if selected_id not in allowed_by_id:
                return self._fallback_or_reject(
                    user=user,
                    workspace_id=workspace_id,
                    policy=policy,
                    requested_mode=requested_mode,
                    requested_id=selected_id or requested_id,
                    allowed_by_id=allowed_by_id,
                    now=now,
                    reason="requested_model_not_authorized_or_available",
                )
            selected, _ = allowed_by_id[selected_id]
            candidates = [selected]
            reason = "authorized_catalog_selection" if requested_id else "administrator_default"

        entitlement = allowed_by_id[selected.id][1]
        effort = self._bounded_effort(
            selected.default_reasoning_effort, selected.maximum_reasoning_effort
        )
        resolved = ResolvedModelSelection(
            requested_mode=requested_mode,
            requested_catalog_model_id=requested_id,
            effective_catalog_model_id=selected.id,
            provider=selected.provider,
            provider_model_id=selected.provider_model_id,
            reasoning_effort=effort,
            selection_source=source,
            policy_decision="allowed",
            policy_decision_reason=reason,
            entitlement_source=entitlement,
            fallback_reason="",
            candidate_model_ids=tuple(item.id for item in candidates),
            routing_factors=factors,
            model_snapshot=_catalog_snapshot(selected),
            configuration_version=policy.configuration_version,
            requested_at=now,
        )
        return self._audit(user, workspace_id, resolved)

    def _fallback_or_reject(
        self,
        *,
        user: UserModel,
        workspace_id: str,
        policy: LLMModelPolicyModel,
        requested_mode: str,
        requested_id: str,
        allowed_by_id: dict[str, tuple[LLMModelCatalogModel, str]],
        now: datetime,
        reason: str,
    ) -> ResolvedModelSelection:
        fallback_allowed = bool(
            self.settings.model_selection_fallback_enabled and policy.fallback_enabled
        )
        fallback = allowed_by_id.get(policy.fallback_model_id or "") if fallback_allowed else None
        if fallback is None:
            denied = ResolvedModelSelection(
                requested_mode=requested_mode,
                requested_catalog_model_id=requested_id,
                effective_catalog_model_id="",
                provider="",
                provider_model_id="",
                reasoning_effort="",
                selection_source="user",
                policy_decision="denied",
                policy_decision_reason=reason,
                entitlement_source="",
                fallback_reason="",
                candidate_model_ids=tuple(allowed_by_id),
                routing_factors={},
                model_snapshot={},
                configuration_version=policy.configuration_version,
                requested_at=now,
            )
            self._audit(user, workspace_id, denied)
            raise ModelSelectionAuthorizationError(
                "The selected model is not permitted or available."
            )
        model, entitlement = fallback
        resolved = ResolvedModelSelection(
            requested_mode=requested_mode,
            requested_catalog_model_id=requested_id,
            effective_catalog_model_id=model.id,
            provider=model.provider,
            provider_model_id=model.provider_model_id,
            reasoning_effort=self._bounded_effort(
                model.default_reasoning_effort, model.maximum_reasoning_effort
            ),
            selection_source="fallback",
            policy_decision="fallback",
            policy_decision_reason=reason,
            entitlement_source=entitlement,
            fallback_reason=reason,
            candidate_model_ids=tuple(allowed_by_id),
            routing_factors={},
            model_snapshot=_catalog_snapshot(model),
            configuration_version=policy.configuration_version,
            requested_at=now,
        )
        return self._audit(user, workspace_id, resolved)

    def _audit(
        self, user: UserModel, workspace_id: str, resolved: ResolvedModelSelection
    ) -> ResolvedModelSelection:
        row = LLMModelSelectionAuditModel(
            organization_id=user.organization_id,
            workspace_id=workspace_id,
            user_id=user.id,
            requested_mode=resolved.requested_mode,
            requested_catalog_model_id=resolved.requested_catalog_model_id or None,
            effective_catalog_model_id=resolved.effective_catalog_model_id or None,
            effective_provider=resolved.provider,
            effective_provider_model_id=resolved.provider_model_id,
            reasoning_effort=resolved.reasoning_effort,
            selection_source=resolved.selection_source,
            policy_decision=resolved.policy_decision,
            policy_decision_reason=resolved.policy_decision_reason,
            entitlement_source=resolved.entitlement_source,
            fallback_reason=resolved.fallback_reason,
            candidate_model_ids_json=json.dumps(resolved.candidate_model_ids),
            routing_factors_json=json.dumps(resolved.routing_factors),
            model_snapshot_json=json.dumps(resolved.model_snapshot),
            configuration_version=resolved.configuration_version,
            requested_at=resolved.requested_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return replace(
            resolved,
            timeout_seconds=self.settings.selected_provider_timeout_seconds,
            max_output_tokens=self.settings.llm_max_output_tokens,
            audit_id=row.id,
        )

    @staticmethod
    def _routing_factors(question: str) -> dict[str, Any]:
        lowered = question.casefold()
        keywords = ("across", "root cause", "contradiction", "multi-step", "procedure", "trace all")
        matched = [keyword for keyword in keywords if keyword in lowered]
        return {
            "question_length": len(question),
            "complexity_keywords": matched,
            "complex": len(question) >= 180 or len(matched) >= 2,
        }

    @staticmethod
    def _bounded_effort(default: str, maximum: str) -> str:
        default_value = default if default in EFFORT_ORDER else "medium"
        maximum_value = maximum if maximum in EFFORT_ORDER else "high"
        return (
            default_value
            if EFFORT_ORDER[default_value] <= EFFORT_ORDER[maximum_value]
            else maximum_value
        )


def selection_metadata(selection: ResolvedModelSelection) -> dict[str, Any]:
    return {
        "requested_model_mode": selection.requested_mode,
        "requested_catalog_model_id": selection.requested_catalog_model_id,
        "effective_catalog_model_id": selection.effective_catalog_model_id,
        "requested_model": selection.requested_catalog_model_id or selection.requested_mode,
        "effective_model": selection.provider_model_id,
        "provider": selection.provider,
        "reasoning_effort": selection.reasoning_effort,
        "selected_by": selection.selection_source,
        "model_policy_decision": selection.policy_decision,
        "model_policy_decision_reason": selection.policy_decision_reason,
        "model_entitlement_source": selection.entitlement_source,
        "fallback_used": selection.selection_source == "fallback",
        "fallback_reason": selection.fallback_reason,
        "model_snapshot": selection.model_snapshot,
        "model_selection_requested_at": selection.requested_at,
        "model_selection_configuration_version": selection.configuration_version,
    }
