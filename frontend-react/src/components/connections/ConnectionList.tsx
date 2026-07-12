import type { ConnectionValidationResult, DatabaseConnection } from "../../models/connection";
import { ConnectionTestResult } from "./ConnectionTestResult";
import { useState } from "react";
import { ConfirmationDialog } from "../common/ConfirmationDialog";
import { EmptyState } from "../common/EmptyState";
import { StatusBadge } from "../common/StatusBadge";

interface ConnectionListProps {
  connections: DatabaseConnection[];
  testingIds: Set<string>;
  testResults: Record<string, ConnectionValidationResult | undefined>;
  testErrors: Record<string, string | undefined>;
  onEdit: (connection: DatabaseConnection, name: string, connectionString?: string) => Promise<void> | void;
  onDelete: (connection: DatabaseConnection) => Promise<void> | void;
  onTest: (connection: DatabaseConnection) => Promise<void> | void;
}

export function ConnectionList({ connections, testingIds, testResults, testErrors, onEdit, onDelete, onTest }: ConnectionListProps) {
  const [pendingDelete, setPendingDelete] = useState<DatabaseConnection | null>(null);
  function edit(connection: DatabaseConnection) {
    const name = window.prompt("Connection name", connection.name);
    if (name === null) return;
    const connectionString = window.prompt("New connection string. Leave blank to keep existing secret.");
    if (connectionString === null) return;
    void onEdit(connection, name.trim(), connectionString.trim() || undefined);
  }

  if (!connections.length) return <EmptyState message="No database connections yet." />;
  return (
    <div className="connection-list">
      <h2>Connection list</h2>
      <table>
        <thead><tr><th>Name</th><th>Engine</th><th>Status</th><th>Test</th><th>Actions</th><th>Result</th></tr></thead>
        <tbody>
          {connections.map((connection) => (
            <tr key={connection.id}>
              <td>{connection.name}</td>
              <td>{connection.engine}</td>
              <td><StatusBadge status={connection.is_active ? "Active" : "Inactive"} /></td>
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
