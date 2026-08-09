import type { ConnectionValidationResult, DatabaseConnection, MetadataCatalogSummary } from "../../models/connection";
import { ConnectionTestResult } from "./ConnectionTestResult";
import { useState } from "react";
import { ConfirmationDialog } from "../common/ConfirmationDialog";
import { EmptyState } from "../common/EmptyState";
import { StatusBadge } from "../common/StatusBadge";
import { environmentLabel } from "../investigation/EnvironmentNotice";
import type { EnvironmentType } from "../../models/connection";

interface ConnectionListProps {
  connections: DatabaseConnection[];
  testingIds: Set<string>;
  testResults: Record<string, ConnectionValidationResult | undefined>;
  testErrors: Record<string, string | undefined>;
  onEdit: (connection: DatabaseConnection, name: string, environment: EnvironmentType, connectionString?: string) => Promise<void> | void;
  onDelete: (connection: DatabaseConnection) => Promise<void> | void;
  onTest: (connection: DatabaseConnection) => Promise<void> | void;
  metadata?: Record<string, MetadataCatalogSummary | undefined>;
  refreshingIds?: Set<string>;
  onRefreshMetadata?: (connection: DatabaseConnection) => Promise<void> | void;
}

export function ConnectionList({ connections, testingIds, testResults, testErrors, onEdit, onDelete, onTest, metadata = {}, refreshingIds = new Set(), onRefreshMetadata = () => undefined }: ConnectionListProps) {
  const [pendingDelete, setPendingDelete] = useState<DatabaseConnection | null>(null);
  function edit(connection: DatabaseConnection) {
    const name = window.prompt("Connection name", connection.name);
    if (name === null) return;
    const connectionString = window.prompt("New connection string. Leave blank to keep existing secret.");
    if (connectionString === null) return;
    const environment = window.prompt(
      "Environment: production, uat, test, evaluation, or demo",
      connection.environment_type,
    ) ?? connection.environment_type;
    if (!["production", "uat", "test", "evaluation", "demo"].includes(environment)) {
      window.alert("Invalid environment.");
      return;
    }
    void onEdit(connection, name.trim(), environment as EnvironmentType, connectionString.trim() || undefined);
  }

  if (!connections.length) return <EmptyState message="No database connections yet." />;
  return (
    <div className="connection-list">
      <h2>Connection list</h2>
      <table>
        <thead><tr><th>Name</th><th>Engine</th><th>Environment</th><th>Status</th><th>Metadata catalog</th><th>Test</th><th>Actions</th><th>Result</th></tr></thead>
        <tbody>
          {connections.map((connection) => (
            <tr key={connection.id}>
              <td>{connection.name}</td>
              <td>{connection.engine}</td>
              <td><strong className="environment-badge">{environmentLabel(connection.environment_type)}</strong> ({connection.max_scan_rows} rows)</td>
              <td><StatusBadge status={connection.is_active ? "Active" : "Inactive"} /></td>
              <td>{(() => { const summary=metadata[connection.id]; const counts=summary?.counts ?? {}; return <><StatusBadge status={summary?.status ?? "NOT_DISCOVERED"} /><div>Version: {summary?.version ?? "—"}</div><div>Tables: {counts.tables ?? 0}; Columns: {counts.columns ?? 0}; Views: {counts.views ?? 0}; Procedures: {counts.procedures ?? 0}; Functions: {counts.functions ?? 0}; Triggers: {counts.triggers ?? 0}; Relationships: {counts.relationships ?? 0}</div><div>Last refresh: {summary?.last_refresh ? new Date(summary.last_refresh).toLocaleString() : "Never"}</div><button type="button" disabled={!connection.is_active || connection.engine !== "sql_server" || refreshingIds.has(connection.id)} onClick={() => void onRefreshMetadata(connection)}>{refreshingIds.has(connection.id) ? "Refreshing..." : "Refresh Metadata"}</button></>; })()}</td>
              <td><button type="button" onClick={() => void onTest(connection)} disabled={!connection.is_active || testingIds.has(connection.id)}>{testingIds.has(connection.id) ? "Testing..." : "Test"}</button></td>
              <td>
                <button type="button" onClick={() => edit(connection)}>Edit</button>
                <button type="button" onClick={() => setPendingDelete(connection)} disabled={!connection.is_active}>Delete</button>
              </td>
              <td><ConnectionTestResult isTesting={testingIds.has(connection.id)} result={testResults[connection.id]} error={testErrors[connection.id]} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <ConfirmationDialog open={Boolean(pendingDelete)} title="Deactivate database connection" message="Deactivate this database connection? Existing history is kept." confirmLabel="Delete" onCancel={() => setPendingDelete(null)} onConfirm={() => { const connection=pendingDelete; setPendingDelete(null); if (connection) void onDelete(connection); }} />
    </div>
  );
}
