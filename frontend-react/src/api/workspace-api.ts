import type { Workspace, WorkspaceCreate, WorkspaceUpdate } from "../models/workspace";
import { ApiClientError, apiRequest } from "./client";

export async function listWorkspaces(
  organizationId: string,
  signal?: AbortSignal,
): Promise<Workspace[]> {
  return (
    (await apiRequest<Workspace[]>(
      `/workspaces?organization_id=${encodeURIComponent(organizationId)}`,
      { signal },
    )) ?? []
  );
}

export async function createWorkspace(payload: WorkspaceCreate): Promise<Workspace> {
  const workspace = await apiRequest<Workspace>("/workspaces", {
    method: "POST",
    body: payload,
  });
  if (!workspace) throw new ApiClientError("Workspace creation returned an empty response.", 201);
  return workspace;
}

export async function updateWorkspace(
  workspaceId: string,
  payload: WorkspaceUpdate,
): Promise<Workspace> {
  const workspace = await apiRequest<Workspace>(`/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: "PATCH",
    body: payload,
  });
  if (!workspace) throw new ApiClientError("Workspace update returned an empty response.", 200);
  return workspace;
}

export async function deleteWorkspace(workspaceId: string): Promise<void> {
  await apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}`, { method: "DELETE" });
}
