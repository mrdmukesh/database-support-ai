import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  createCatalogModel,
  loadCatalog,
  loadModelPolicy,
  loadSelectionAudit,
  updateCatalogModel,
  updateModelPolicy,
  loadUserModelAccess,
  updateUserModelAccess,
  type CatalogModel,
  type ModelPolicy,
} from "../../api/model-management-api";
import { useAuth } from "../../hooks/use-auth";
import { Alert, Card, FormField, PrimaryButton, Select } from "../../components/ui";

export function ModelManagementPage() {
  const { organizationId, user } = useAuth();
  const allowed = user?.role === "super_admin" || user?.role === "organization_admin";
  const [models, setModels] = useState<CatalogModel[]>([]);
  const [policy, setPolicy] = useState<ModelPolicy | null>(null);
  const [audit, setAudit] = useState<Array<Record<string, string>>>([]);
  const [error, setError] = useState("");
  const [accessExplanation, setAccessExplanation] = useState("");

  const refresh = useCallback(async () => {
    if (!organizationId || !allowed) return;
    try {
      const [catalog, nextPolicy, auditResult] = await Promise.all([
        loadCatalog(organizationId), loadModelPolicy(organizationId), loadSelectionAudit(organizationId),
      ]);
      setModels(catalog ?? []);
      setPolicy(nextPolicy ?? null);
      setAudit(auditResult?.items ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Model management could not be loaded.");
    }
  }, [allowed, organizationId]);

  useEffect(() => { void refresh(); }, [refresh]);

  if (!allowed) return <Alert title="Administrator access required">You are not authorized to manage models.</Alert>;

  async function addModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    const data = new FormData(event.currentTarget);
    await createCatalogModel({
      organization_id: organizationId,
      display_name: String(data.get("display_name") || ""),
      provider: String(data.get("provider") || ""),
      provider_model_id: String(data.get("provider_model_id") || ""),
      model_category: String(data.get("model_category") || "custom") as CatalogModel["model_category"],
      description: String(data.get("description") || ""), enabled: true,
      default_reasoning_effort: "medium", maximum_reasoning_effort: "high",
      context_limit: null, cost_tier: "standard", latency_tier: "standard",
      recommended_usage: "", availability_status: "available", retirement_date: null,
      sort_order: 100, premium: false, automatic_eligible: false,
    });
    event.currentTarget.reset();
    await refresh();
  }

  return <section className="ui-page" aria-labelledby="model-management-title">
    <header className="ui-page-header"><div><p className="eyebrow">AI governance</p><h2 id="model-management-title">Model Management</h2><p>Control the approved model catalog, access policy, and selection audit without exposing provider credentials.</p></div></header>
    {error ? <Alert title="Model management error">{error}</Alert> : null}
    <Card title="Model catalog" description="Only enabled and available models can be selected.">
      <div className="ui-table-wrapper"><table><thead><tr><th>Model</th><th>Category</th><th>Availability</th><th>Premium</th><th>Automatic</th><th>Enabled</th></tr></thead><tbody>
        {models.map((model) => <tr key={model.id}><td><strong>{model.display_name}</strong><small>{model.description}</small><button type="button" onClick={() => void updateModelPolicy(organizationId!, { global_default_model_id: model.id }).then(refresh)}>Set default</button></td><td>{model.model_category}</td><td>{model.availability_status}</td><td><button type="button" onClick={() => void updateCatalogModel(model.id, { premium: !model.premium }).then(refresh)}>{model.premium ? "Approval required" : "Standard"}</button></td><td><button type="button" onClick={() => void updateCatalogModel(model.id, { automatic_eligible: !model.automatic_eligible }).then(refresh)}>{model.automatic_eligible ? "Eligible" : "No"}</button></td><td><button type="button" onClick={() => void updateCatalogModel(model.id, { enabled: !model.enabled }).then(refresh)} aria-label={`${model.enabled ? "Disable" : "Enable"} ${model.display_name}`}>{model.enabled ? "Enabled" : "Disabled"}</button></td></tr>)}
      </tbody></table></div>
      <form onSubmit={addModel} aria-label="Add model configuration">
        <FormField label="Display name" htmlFor="model-display-name"><input id="model-display-name" name="display_name" required /></FormField>
        <FormField label="Provider" htmlFor="model-provider"><input id="model-provider" name="provider" required /></FormField>
        <FormField label="Provider model ID" htmlFor="provider-model-id" hint="Visible only to administrators."><input id="provider-model-id" name="provider_model_id" required /></FormField>
        <FormField label="Category" htmlFor="model-category"><Select id="model-category" name="model_category"><option value="fast">Fast</option><option value="deep_analysis">Deep Analysis</option><option value="custom">Custom</option></Select></FormField>
        <PrimaryButton type="submit">Add model</PrimaryButton>
      </form>
    </Card>
    <Card title="Access policy" description="Changes are enforced again by the server for every investigation.">
      {policy ? <div className="model-policy-controls">
        <label><input type="checkbox" checked={policy.user_selection_enabled} onChange={(event) => void updateModelPolicy(organizationId!, { user_selection_enabled: event.target.checked }).then(refresh)} /> User model selection</label>
        <label><input type="checkbox" checked={policy.automatic_mode_enabled} onChange={(event) => void updateModelPolicy(organizationId!, { automatic_mode_enabled: event.target.checked }).then(refresh)} /> Automatic mode</label>
        <label><input type="checkbox" checked={policy.fallback_enabled} onChange={(event) => void updateModelPolicy(organizationId!, { fallback_enabled: event.target.checked }).then(refresh)} /> Audited fallback</label>
        <label><input type="checkbox" checked={policy.require_premium_approval} onChange={(event) => void updateModelPolicy(organizationId!, { require_premium_approval: event.target.checked }).then(refresh)} /> Require premium approval</label>
      </div> : <p>No organization policy exists yet. Saving a policy through the API creates one safely disabled.</p>}
      <form aria-label="User model access" onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const userId = String(data.get("user_id") || "");
        const workspaceId = String(data.get("workspace_id") || "");
        const modelId = String(data.get("model_id") || "");
        const expires = String(data.get("expires_at") || "");
        const allowed = String(data.get("access_action") || "grant") === "grant";
        void updateUserModelAccess(userId, organizationId!, [{ model_id: modelId, allowed, approval_expires_at: expires || null }])
          .then(() => loadUserModelAccess(userId, workspaceId, "production"))
          .then((result) => setAccessExplanation(`Effective access: ${result?.options.map((item) => item.display_name).join(", ") || "none"}. Role: ${result?.role || "unknown"}.`));
      }}>
        <FormField label="User ID" htmlFor="model-access-user"><input id="model-access-user" name="user_id" required /></FormField>
        <FormField label="Workspace ID" htmlFor="model-access-workspace"><input id="model-access-workspace" name="workspace_id" required /></FormField>
        <FormField label="Approved model" htmlFor="model-access-model"><Select id="model-access-model" name="model_id">{models.map((model) => <option key={model.id} value={model.id}>{model.display_name}{model.premium ? " — premium approval" : ""}</option>)}</Select></FormField>
        <FormField label="Access action" htmlFor="model-access-action"><Select id="model-access-action" name="access_action"><option value="grant">Grant or approve</option><option value="revoke">Revoke</option></Select></FormField>
        <FormField label="Approval expiration" htmlFor="model-access-expiration" hint="Optional ISO timestamp for time-bounded premium access."><input id="model-access-expiration" name="expires_at" type="datetime-local" /></FormField>
        <PrimaryButton type="submit">Grant access</PrimaryButton>
      </form>
      {accessExplanation ? <p aria-live="polite">{accessExplanation}</p> : null}
    </Card>
    <Card title="Selection audit" description="Requested versus effective selections and policy decisions.">
      <div className="ui-table-wrapper"><table><thead><tr><th>Time</th><th>User</th><th>Requested</th><th>Effective</th><th>Decision</th><th>Reason</th></tr></thead><tbody>{audit.map((item) => <tr key={item.id}><td>{String(item.requested_at || "")}</td><td>{item.user_id}</td><td>{item.requested_catalog_model_id || item.requested_mode}</td><td>{item.effective_catalog_model_id}</td><td>{item.policy_decision}</td><td>{item.policy_decision_reason}</td></tr>)}</tbody></table></div>
    </Card>
  </section>;
}
