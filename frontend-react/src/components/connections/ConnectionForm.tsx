import { useState, type FormEvent } from "react";
import type { DatabaseConnectionCreate } from "../../models/connection";
import type { EnvironmentType } from "../../models/connection";
import type { Workspace } from "../../models/workspace";

interface ConnectionFormProps {
  organizationId: string;
  workspaces: Workspace[];
  isSubmitting: boolean;
  onSubmit: (payload: DatabaseConnectionCreate) => Promise<void> | void;
}

export function ConnectionForm({ organizationId, workspaces, isSubmitting, onSubmit }: ConnectionFormProps) {
  const [formKey, setFormKey] = useState(0);
  const [environment, setEnvironment] = useState<EnvironmentType>("production");
  const [maxScanRows, setMaxScanRows] = useState(100);

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
      environment_type: String(form.get("environmentType") ?? "production") as DatabaseConnectionCreate["environment_type"],
      max_scan_rows: Number(form.get("maxScanRows") ?? 500),
    });
    setFormKey((value) => value + 1);
    setEnvironment("production");
    setMaxScanRows(100);
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
      <label htmlFor="connection-environment">Trusted environment</label>
      <select id="connection-environment" name="environmentType" value={environment} disabled={isSubmitting}
        onChange={(event) => {
          const value = event.target.value as EnvironmentType;
          setEnvironment(value);
          setMaxScanRows(value === "production" ? 100 : value === "uat" ? 500 : 1000);
        }}>
        <option value="production">Production</option>
        <option value="uat">UAT</option>
        <option value="test">Test</option>
        <option value="evaluation">Evaluation</option>
        <option value="demo">Demo</option>
      </select>
      <label htmlFor="connection-max-scan-rows">Maximum bounded scan rows</label>
      <input id="connection-max-scan-rows" name="maxScanRows" type="number" min="1" max="5000" value={maxScanRows} onChange={(event) => setMaxScanRows(Number(event.target.value))} disabled={isSubmitting} />
      <div className="field-note environment-help">
        <p><strong>Production:</strong> Strict read-only investigation policy. Some sensitive, unrestricted, or expensive evidence queries may be blocked.</p>
        <p><strong>UAT:</strong> Read-only investigation with broader bounded evidence collection. Data and schema changes remain prohibited.</p>
        <p><strong>Test:</strong> Read-only investigation with broader metadata, relationship, and bounded table analysis. Data and schema changes remain prohibited.</p>
        <p><strong>Demo / Evaluation:</strong> Benchmark and evaluation mode. Broader read-only evidence collection is allowed using bounded scans. DML and DDL remain prohibited.</p>
      </div>
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
