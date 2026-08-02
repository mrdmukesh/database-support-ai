import { useEffect, useState, type FormEvent } from "react";

import { loadAvailableModels, submitInvestigation } from "../../api/investigation-api";
import { useInvestigation } from "../../features/investigation/use-investigation";
import { useAuth } from "../../hooks/use-auth";
import type { DatabaseConnection } from "../../models/connection";
import type { Workspace } from "../../models/workspace";
import type { AvailableModelsResponse } from "../../models/investigation";
import { Alert, Card, FormField, InvestigationProgress, PrimaryButton, Select, Textarea } from "../ui";
import { EnvironmentNotice, environmentLabel } from "./EnvironmentNotice";

interface InvestigationFormProps {
  workspaces: Workspace[];
  connections: DatabaseConnection[];
}

export function InvestigationForm({ workspaces, connections }: InvestigationFormProps) {
  const { organizationId, user } = useAuth();
  const investigation = useInvestigation();
  const [question, setQuestion] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [modelPolicy, setModelPolicy] = useState<AvailableModelsResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState("");

  const availableWorkspaces = workspaces.filter((workspace) => workspace.is_active);
  const availableConnections = connections.filter(
    (connection) =>
      connection.is_active && connection.workspace_id === investigation.selectedWorkspaceId,
  );
  const selectedConnection = availableConnections.find(
    (connection) => connection.id === investigation.selectedConnectionId,
  );

  useEffect(() => {
    if (!investigation.selectedWorkspaceId || !selectedConnection) {
      setModelPolicy(null);
      setSelectedModel("");
      return;
    }
    const controller = new AbortController();
    loadAvailableModels(
      investigation.selectedWorkspaceId,
      selectedConnection.environment_type,
      controller.signal,
    )
      .then((policy) => {
        setModelPolicy(policy);
        setSelectedModel(policy.default_value);
      })
      .catch(() => {
        setModelPolicy(null);
        setSelectedModel("");
      });
    return () => controller.abort();
  }, [investigation.selectedWorkspaceId, selectedConnection]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();

    if (!investigation.selectedWorkspaceId) {
      setValidationError("Select a workspace.");
      return;
    }
    if (!investigation.selectedConnectionId || !selectedConnection) {
      setValidationError("Select an active database connection for this workspace.");
      return;
    }
    if (!trimmedQuestion) {
      setValidationError("Enter an investigation question.");
      return;
    }
    if (!organizationId || !user) {
      setValidationError("An authenticated session is required.");
      return;
    }

    setValidationError(null);
    investigation.startSubmission(trimmedQuestion);

    try {
      const response = await submitInvestigation({
        organization_id: organizationId,
        workspace_id: investigation.selectedWorkspaceId,
        connection_id: investigation.selectedConnectionId,
        environment_type: selectedConnection.environment_type,
        user_id: user.id,
        question: trimmedQuestion,
        model_selection_mode: selectedModel === "automatic" ? "automatic" : selectedModel ? "model" : null,
        catalog_model_id: selectedModel && selectedModel !== "automatic" ? selectedModel : null,
      });
      investigation.completeSubmission(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Investigation submission failed.";
      investigation.failSubmission(message);
      setValidationError(message);
    }
  }

  return (
    <form className="investigation-form" onSubmit={handleSubmit} aria-label="Investigation form" noValidate>
      <Card title="Investigation scope" description="Choose the exact workspace and active database connection the evidence collector must use.">
      <div className="investigation-scope-grid">
      <FormField label="Workspace" htmlFor="investigation-workspace" required>
        <Select id="investigation-workspace"
          aria-label="Workspace"
          value={investigation.selectedWorkspaceId ?? ""}
          onChange={(event) => investigation.selectWorkspace(event.target.value || null)}
          disabled={investigation.isLoading}
          required
        >
          <option value="">Select a workspace</option>
          {availableWorkspaces.map((workspace) => (
            <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
          ))}
        </Select>
      </FormField>

      {selectedConnection ? (
        <><aside className="connection-summary" aria-label="Selected connection summary">
          <div><span>Selected connection</span><strong>{selectedConnection.name}</strong></div>
          <dl><dt>Engine</dt><dd>{selectedConnection.engine}</dd><dt>Environment</dt><dd>{environmentLabel(selectedConnection.environment_type)}</dd><dt>Status</dt><dd><span className="connection-live-dot" /> Active</dd><dt>Access</dt><dd>Read-only investigation</dd></dl>
          <small>Connection ID: {selectedConnection.id}</small>
        </aside><EnvironmentNotice environment={selectedConnection.environment_type} /></>
      ) : null}

      <FormField label="Database connection" htmlFor="investigation-connection" hint="Only active connections in the selected workspace are available." required>
        <Select id="investigation-connection"
          aria-label="Database connection"
          value={investigation.selectedConnectionId ?? ""}
          onChange={(event) => investigation.selectConnection(event.target.value || null)}
          disabled={investigation.isLoading || !investigation.selectedWorkspaceId}
          required
        >
          <option value="">Select a database connection</option>
          {availableConnections.map((connection) => (
            <option key={connection.id} value={connection.id}>{connection.name}</option>
          ))}
        </Select>
      </FormField>
      </div></Card>

      {modelPolicy?.selection_enabled ? (
        <Card title="Analysis model" description="Choose only from models approved by your administrator. Safety and evidence controls are identical for every option.">
          <FormField label="Model" htmlFor="investigation-model" hint="Automatic is recommended when enabled.">
            <Select
              id="investigation-model"
              aria-label="Analysis model"
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
              disabled={investigation.isLoading}
            >
              {modelPolicy.options.map((option) => (
                <option key={option.value} value={option.value} disabled={option.disabled}>
                  {option.display_name} — {option.latency_tier} speed · {option.cost_tier} cost
                </option>
              ))}
            </Select>
          </FormField>
          {modelPolicy.options.find((option) => option.value === selectedModel) ? (
            <p className="model-selection-description" aria-live="polite">
              {modelPolicy.options.find((option) => option.value === selectedModel)?.description}
              {" "}{modelPolicy.options.find((option) => option.value === selectedModel)?.recommended_usage}
            </p>
          ) : null}
        </Card>
      ) : null}

      <Card title="Describe the database issue" description="Include a business identifier, observed behavior, and what you expected to happen.">
      <FormField label="Investigation question" htmlFor="investigation-question" hint="Example: Payment PAY-9001 was processed twice after retry job execution. Investigate duplicate payment creation." required>
        <Textarea id="investigation-question"
          aria-label="Question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={investigation.isLoading}
          placeholder="Describe the production symptom, affected record, and expected behavior…"
          maxLength={4000}
          required
        />
      </FormField></Card>

      {(validationError || investigation.currentError) && (
        <Alert title="Investigation could not start">{validationError ?? investigation.currentError}</Alert>
      )}
      {investigation.isLoading ? (
        <Card title="Investigation in progress" description="Evidence collection is read-only. Keep this page open while the analysis completes."><InvestigationProgress stages={[
          { label: "Request validation", state: "completed" }, { label: "Connection confirmation", state: "completed" },
          { label: "Metadata discovery", state: "active" }, { label: "Evidence planning", state: "pending" },
          { label: "Evidence collection", state: "pending" }, { label: "Evidence verification", state: "pending" },
          { label: "Root-cause analysis", state: "pending" }, { label: "Report generation", state: "pending" },
        ]} /></Card>
      ) : null}
      <div className="investigation-form-actions"><PrimaryButton type="submit" disabled={investigation.isLoading}>
        {investigation.isLoading ? "Starting investigation…" : "Start Investigation"}
      </PrimaryButton><span>All database queries are validated as read-only.</span></div>
    </form>
  );
}
