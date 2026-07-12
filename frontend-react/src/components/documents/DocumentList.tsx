import type { DocumentSummary } from "../../models/document";
import type { Workspace } from "../../models/workspace";

interface DocumentListProps {
  documents: DocumentSummary[];
  workspaces: Workspace[];
}

export function DocumentList({ documents, workspaces }: DocumentListProps) {
  const workspaceNames = new Map(workspaces.map((workspace) => [workspace.id, workspace.name]));
  if (!documents.length) return <p className="empty-state">No documents yet.</p>;
  return (
    <div className="document-list">
      <h2>Document list</h2>
      <table>
        <thead><tr><th>Title</th><th>Version</th><th>Workspace</th></tr></thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id}>
              <td>{document.title}</td>
              <td>{document.current_version}</td>
              <td>{workspaceNames.get(document.workspace_id) ?? "Unknown"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
