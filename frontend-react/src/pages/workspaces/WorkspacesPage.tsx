import { useCallback, useEffect, useState } from "react";
import {
  createWorkspace,
  deleteWorkspace,
  listWorkspaces,
  updateWorkspace,
} from "../../api/workspace-api";
import { WorkspaceForm, type WorkspaceFormValue } from "../../components/workspaces/WorkspaceForm";
import { WorkspaceList } from "../../components/workspaces/WorkspaceList";
import { useAuth } from "../../hooks/use-auth";
import type { Workspace } from "../../models/workspace";

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Workspace request failed.";
}

export function WorkspacesPage() {
  const { organizationId } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!organizationId) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await listWorkspaces(organizationId, signal);
      setWorkspaces(result);
      setMessage(result.length ? "Workspaces loaded." : "No workspaces yet.");
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setError(messageOf(cause));
    } finally {
      setIsLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function create(value: WorkspaceFormValue) {
    if (!organizationId) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await createWorkspace({ organization_id: organizationId, ...value });
      setMessage("Workspace created.");
      await load();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function edit(workspace: Workspace, name: string, slug: string) {
    setError(null);
    try {
      await updateWorkspace(workspace.id, { name, slug });
      setMessage("Workspace updated.");
      await load();
    } catch (cause) {
      setError(messageOf(cause));
    }
  }

  async function remove(workspace: Workspace) {
    setError(null);
    try {
      await deleteWorkspace(workspace.id);
      setMessage("Workspace deactivated.");
      await load();
    } catch (cause) {
      setError(messageOf(cause));
    }
  }

  return (
    <section className="management-page" aria-labelledby="workspaces-page-title">
      <div className="management-page-heading">
        <p className="eyebrow">Administration</p>
        <h2 id="workspaces-page-title">Workspaces</h2>
      </div>
      {error ? <div className="form-message error" role="alert">{error}</div> : null}
      {!error && message ? <div className="form-message" role="status">{message}</div> : null}
      <div className="management-grid">
        <WorkspaceForm isSubmitting={isSubmitting} onSubmit={create} />
        {isLoading ? <p>Loading workspaces...</p> : (
          <WorkspaceList workspaces={workspaces} onEdit={edit} onDelete={remove} />
        )}
      </div>
    </section>
  );
}
