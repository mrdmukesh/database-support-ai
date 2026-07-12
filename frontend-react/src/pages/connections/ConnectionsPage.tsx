import { useCallback, useEffect, useState } from "react";
import { createConnection, deleteConnection, listConnections, testConnection, updateConnection } from "../../api/connection-api";
import { listWorkspaces } from "../../api/workspace-api";
import { ConnectionForm } from "../../components/connections/ConnectionForm";
import { ConnectionList } from "../../components/connections/ConnectionList";
import { useAuth } from "../../hooks/use-auth";
import type { ConnectionValidationResult, DatabaseConnection, DatabaseConnectionCreate } from "../../models/connection";
import type { Workspace } from "../../models/workspace";

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Database connection request failed.";
}

export function ConnectionsPage() {
  const { organizationId } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [workspaceFilter, setWorkspaceFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testingIds, setTestingIds] = useState<Set<string>>(new Set());
  const [testResults, setTestResults] = useState<Record<string, ConnectionValidationResult | undefined>>({});
  const [testErrors, setTestErrors] = useState<Record<string, string | undefined>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!organizationId) return;
    setIsLoading(true);
    setError(null);
    try {
      const [workspaceRows, connectionRows] = await Promise.all([
        listWorkspaces(organizationId, signal),
        listConnections(organizationId, workspaceFilter || undefined, signal),
      ]);
      setWorkspaces(workspaceRows);
      setConnections(connectionRows);
      setMessage("Database connections loaded.");
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setError(messageOf(cause));
    } finally {
      setIsLoading(false);
    }
  }, [organizationId, workspaceFilter]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function create(payload: DatabaseConnectionCreate) {
    setIsSubmitting(true);
    setError(null);
    try {
      await createConnection(payload);
      setMessage("Database connection added.");
      await load();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function edit(connection: DatabaseConnection, name: string, connectionString?: string) {
    const payload = { name, ...(connectionString ? { connection_string: connectionString } : {}) };
    try {
      await updateConnection(connection.id, payload);
      setMessage("Database connection updated.");
      await load();
    } catch (cause) {
      setError(messageOf(cause));
    }
  }

  async function remove(connection: DatabaseConnection) {
    try {
      await deleteConnection(connection.id);
      setMessage("Database connection deactivated.");
      await load();
    } catch (cause) {
      setError(messageOf(cause));
    }
  }

  async function validate(connection: DatabaseConnection) {
    setTestingIds((current) => new Set(current).add(connection.id));
    setTestErrors((current) => ({ ...current, [connection.id]: undefined }));
    try {
      const result = await testConnection(connection.id);
      setTestResults((current) => ({ ...current, [connection.id]: result }));
    } catch (cause) {
      setTestErrors((current) => ({ ...current, [connection.id]: messageOf(cause) }));
    } finally {
      setTestingIds((current) => {
        const next = new Set(current);
        next.delete(connection.id);
        return next;
      });
    }
  }

  return (
    <section className="management-page" aria-labelledby="connections-page-title">
      <div className="management-page-heading"><p className="eyebrow">Administration</p><h2 id="connections-page-title">Connections</h2></div>
      {error ? <div className="form-message error" role="alert">{error}</div> : null}
      {!error && message ? <div className="form-message" role="status">{message}</div> : null}
      <label htmlFor="connection-workspace-filter">Filter by workspace</label>
      <select id="connection-workspace-filter" value={workspaceFilter} onChange={(event) => setWorkspaceFilter(event.target.value)}>
        <option value="">All workspaces</option>
        {workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
      </select>
      <div className="management-grid connections-grid">
        <ConnectionForm organizationId={organizationId ?? ""} workspaces={workspaces} isSubmitting={isSubmitting} onSubmit={create} />
        {isLoading ? <p>Loading database connections...</p> : (
          <ConnectionList connections={connections} testingIds={testingIds} testResults={testResults} testErrors={testErrors} onEdit={edit} onDelete={remove} onTest={validate} />
        )}
      </div>
    </section>
  );
}
