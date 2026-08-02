import { apiRequest } from "./client";

export interface CatalogModel {
  id: string;
  organization_id: string;
  display_name: string;
  provider: string;
  provider_model_id: string;
  model_category: "fast" | "deep_analysis" | "custom";
  description: string;
  enabled: boolean;
  default_reasoning_effort: string;
  maximum_reasoning_effort: string;
  context_limit: number | null;
  cost_tier: string;
  latency_tier: string;
  recommended_usage: string;
  availability_status: string;
  retirement_date: string | null;
  sort_order: number;
  premium: boolean;
  automatic_eligible: boolean;
  configuration_version: number;
}

export interface ModelPolicy {
  id: string;
  organization_id: string;
  user_selection_enabled: boolean;
  automatic_mode_enabled: boolean;
  admin_management_enabled: boolean;
  global_default_model_id: string | null;
  automatic_candidate_ids: string[];
  fallback_model_id: string | null;
  fallback_enabled: boolean;
  require_premium_approval: boolean;
  allowed_environments: string[];
  selection_roles: string[];
  configuration_version: number;
}

export const loadCatalog = (organizationId: string) =>
  apiRequest<CatalogModel[]>(`/admin/models?organization_id=${encodeURIComponent(organizationId)}`);

export const createCatalogModel = (payload: Omit<CatalogModel, "id" | "configuration_version">) =>
  apiRequest<CatalogModel>("/admin/models", { method: "POST", body: payload });

export const updateCatalogModel = (id: string, payload: Partial<CatalogModel>) =>
  apiRequest<CatalogModel>(`/admin/models/${encodeURIComponent(id)}`, { method: "PATCH", body: payload });

export const loadModelPolicy = (organizationId: string) =>
  apiRequest<ModelPolicy>(`/admin/model-policies?organization_id=${encodeURIComponent(organizationId)}`);

export const updateModelPolicy = (organizationId: string, payload: Partial<ModelPolicy>) =>
  apiRequest<ModelPolicy>(`/admin/model-policies/${encodeURIComponent(organizationId)}`, { method: "PATCH", body: payload });

export const loadSelectionAudit = (organizationId: string) =>
  apiRequest<{ items: Array<Record<string, string>>; total: number }>(
    `/admin/model-selection-audit?organization_id=${encodeURIComponent(organizationId)}`,
  );

export const loadUserModelAccess = (userId: string, workspaceId: string, environment: string) => {
  const query = new URLSearchParams({ workspace_id: workspaceId, environment });
  return apiRequest<{ user_id: string; role: string; options: Array<{ value: string; display_name: string }> }>(
    `/admin/users/${encodeURIComponent(userId)}/model-access?${query}`,
  );
};

export const updateUserModelAccess = (
  userId: string,
  organizationId: string,
  entitlements: Array<{ model_id: string; allowed: boolean; approval_expires_at?: string | null }>,
) => apiRequest(`/admin/users/${encodeURIComponent(userId)}/model-access`, {
  method: "PUT", body: { organization_id: organizationId, entitlements },
});
