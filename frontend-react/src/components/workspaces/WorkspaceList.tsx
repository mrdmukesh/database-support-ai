import type { Workspace } from "../../models/workspace";

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
  function edit(workspace: Workspace) {
    const name = window.prompt("Workspace name", workspace.name);
    if (name === null) return;
    const slug = window.prompt("Workspace slug", workspace.slug);
    if (slug === null) return;
    void onEdit(workspace, name.trim(), slug.trim());
  }

  function remove(workspace: Workspace) {
    if (!window.confirm("Deactivate this workspace? Existing history is kept.")) return;
    void onDelete(workspace);
  }

  if (!workspaces.length) return <p className="empty-state">No workspaces yet.</p>;

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
              <td>{workspace.is_active ? "Active" : "Inactive"}</td>
              <td>
                {onSelect ? (
                  <button type="button" onClick={() => onSelect(workspace)}>
                    {selectedWorkspaceId === workspace.id ? "Selected" : "Select"}
                  </button>
                ) : null}
                <button type="button" onClick={() => edit(workspace)}>Edit</button>
                <button type="button" onClick={() => remove(workspace)} disabled={!workspace.is_active}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
