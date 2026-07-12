import type { Workspace } from "../../models/workspace";
import { useState } from "react";
import { ConfirmationDialog } from "../common/ConfirmationDialog";
import { EmptyState } from "../common/EmptyState";
import { StatusBadge } from "../common/StatusBadge";

interface WorkspaceListProps {
  workspaces: Workspace[];
  selectedWorkspaceId?: string | null;
  onSelect?: (workspace: Workspace) => void;
  onEdit: (workspace: Workspace, name: string, slug: string) => Promise<void> | void;
  onDelete: (workspace: Workspace) => Promise<void> | void;
}

export function WorkspaceList({
  workspaces,
  selectedWorkspaceId,
  onSelect,
  onEdit,
  onDelete,
}: WorkspaceListProps) {
  const [pendingDelete, setPendingDelete] = useState<Workspace | null>(null);
  function edit(workspace: Workspace) {
    const name = window.prompt("Workspace name", workspace.name);
    if (name === null) return;
    const slug = window.prompt("Workspace slug", workspace.slug);
    if (slug === null) return;
    void onEdit(workspace, name.trim(), slug.trim());
  }

  if (!workspaces.length) return <EmptyState message="No workspaces yet." />;

  return (
    <div className="workspace-list">
      <h2>Workspace list</h2>
      <table>
        <thead>
          <tr><th>Name</th><th>Slug</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {workspaces.map((workspace) => (
            <tr key={workspace.id} aria-selected={selectedWorkspaceId === workspace.id || undefined}>
              <td>{workspace.name}</td>
              <td>{workspace.slug}</td>
              <td><StatusBadge status={workspace.is_active ? "Active" : "Inactive"} /></td>
              <td>
                {onSelect ? (
                  <button type="button" onClick={() => onSelect(workspace)}>
                    {selectedWorkspaceId === workspace.id ? "Selected" : "Select"}
                  </button>
                ) : null}
                <button type="button" onClick={() => edit(workspace)}>Edit</button>
                <button type="button" onClick={() => setPendingDelete(workspace)} disabled={!workspace.is_active}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ConfirmationDialog open={Boolean(pendingDelete)} title="Deactivate workspace" message="Deactivate this workspace? Existing history is kept." confirmLabel="Delete" onCancel={() => setPendingDelete(null)} onConfirm={() => { const workspace=pendingDelete; setPendingDelete(null); if (workspace) void onDelete(workspace); }} />
    </div>
  );
}
