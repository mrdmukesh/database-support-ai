import { useState, type FormEvent } from "react";

import { submitInvestigation } from "../../api/investigation-api";
import { useInvestigation } from "../../features/investigation/use-investigation";
import { useAuth } from "../../hooks/use-auth";
import type { DatabaseConnection } from "../../models/connection";
import type { Workspace } from "../../models/workspace";

interface InvestigationFormProps {
  workspaces: Workspace[];
  connections: DatabaseConnection[];
}

export function InvestigationForm({ workspaces, connections }: InvestigationFormProps) {
  const { organizationId, user } = useAuth();
  const investigation = useInvestigation();
  const [question, setQuestion] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const availableWorkspaces = workspaces.filter((workspace) => workspace.is_active);
  const availableConnections = connections.filter(
    (connection) =>
      connection.is_active && connection.workspace_id === investigation.selectedWorkspaceId,
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();

    if (!investigation.selectedWorkspaceId) {
      setValidationError("Select a workspace.");
      return;
    }
    if (!investigation.selectedConnectionId) {
      setValidationError("Select a database connection.");
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
        user_id: user.id,
        question: trimmedQuestion,
      });
      investigation.completeSubmission(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Investigation submission failed.";
      investigation.failSubmission(message);
      setValidationError(message);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Investigation form" noValidate>
      <label>
        Workspace
        <select
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
        </select>
      </label>

      <label>
        Database connection
        <select
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
        </select>
      </label>

      <label>
        Question
        <textarea
          aria-label="Question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={investigation.isLoading}
          maxLength={4000}
          required
        />
      </label>

      {(validationError || investigation.currentError) && (
        <div role="alert">{validationError ?? investigation.currentError}</div>
      )}
      <button type="submit" disabled={investigation.isLoading}>
        {investigation.isLoading ? "Analyzing..." : "Ask AI"}
      </button>
    </form>
  );
}
