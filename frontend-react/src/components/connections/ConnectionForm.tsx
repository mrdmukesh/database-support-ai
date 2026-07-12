import { useState, type FormEvent } from "react";
import type { DatabaseConnectionCreate } from "../../models/connection";
import type { Workspace } from "../../models/workspace";

interface ConnectionFormProps {
  organizationId: string;
  workspaces: Workspace[];
  isSubmitting: boolean;
  onSubmit: (payload: DatabaseConnectionCreate) => Promise<void> | void;
}

export function ConnectionForm({ organizationId, workspaces, isSubmitting, onSubmit }: ConnectionFormProps) {
  const [formKey, setFormKey] = useState(0);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const connectionString = String(form.get("connectionString") ?? "").trim();
    await onSubmit({
      organization_id: organizationId,
      workspace_id: String(form.get("workspaceId") ?? ""),
      engine: String(form.get("engine") ?? ""),
      name: String(form.get("connectionName") ?? "").trim(),
      host: String(form.get("host") ?? "").trim(),
      port: form.get("port") ? Number(form.get("port")) : null,
      database_name: String(form.get("databaseName") ?? "").trim(),
      secret_ref: String(form.get("secretRef") ?? "").trim(),
      connection_string: connectionString || null,
    });
    setFormKey((value) => value + 1);
  }

  return (
    <form key={formKey} className="connection-form" onSubmit={handleSubmit}>
      <h2>Add database connection</h2>
      <label htmlFor="connection-workspace">Workspace</label>
      <select id="connection-workspace" name="workspaceId" required disabled={isSubmitting || !workspaces.length}>
        {workspaces.length ? workspaces.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
        )) : <option value="">Create a workspace first</option>}
      </select>
      <label htmlFor="connection-engine">Engine</label>
      <select id="connection-engine" name="engine" defaultValue="sql_server" disabled={isSubmitting}>
        <option value="sql_server">SQL Server</option>
        <option value="postgresql">PostgreSQL</option>
        <option value="mysql">MySQL</option>
        <option value="sqlite">SQLite</option>
        <option value="oracle">Oracle</option>
      </select>
      <label htmlFor="connection-name">Connection name</label>
      <input id="connection-name" name="connectionName" required disabled={isSubmitting} />
      <label htmlFor="connection-host">Host</label>
      <input id="connection-host" name="host" disabled={isSubmitting} />
      <label htmlFor="connection-port">Port</label>
      <input id="connection-port" name="port" type="number" disabled={isSubmitting} />
      <label htmlFor="connection-database">Database name</label>
      <input id="connection-database" name="databaseName" disabled={isSubmitting} />
      <label htmlFor="connection-string">Connection string</label>
      <input id="connection-string" name="connectionString" type="password" autoComplete="off" disabled={isSubmitting} />
      <label htmlFor="connection-secret-ref">Secret reference</label>
      <input id="connection-secret-ref" name="secretRef" placeholder="env://TARGET_DATABASE_URL" autoComplete="off" disabled={isSubmitting} />
      <p className="field-note">Secret values are submitted only for secure backend storage and are never displayed in the connection list.</p>
      <button type="submit" disabled={isSubmitting || !workspaces.length}>
        {isSubmitting ? "Adding..." : "Add connection"}
      </button>
    </form>
  );
}
