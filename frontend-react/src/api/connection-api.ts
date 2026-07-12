import type {
  ConnectionValidationResult,
  DatabaseConnection,
  DatabaseConnectionCreate,
  DatabaseConnectionUpdate,
} from "../models/connection";
import { ApiClientError, apiRequest } from "./client";

export async function listConnections(
  organizationId: string,
  workspaceId?: string,
  signal?: AbortSignal,
): Promise<DatabaseConnection[]> {
  const query = new URLSearchParams({ organization_id: organizationId });
  if (workspaceId) query.set("workspace_id", workspaceId);
  return (await apiRequest<DatabaseConnection[]>(`/databases/connections?${query}`, { signal })) ?? [];
}

export async function createConnection(
  payload: DatabaseConnectionCreate,
): Promise<DatabaseConnection> {
  const connection = await apiRequest<DatabaseConnection>("/databases/connections", {
    method: "POST",
    body: payload,
  });
  if (!connection) throw new ApiClientError("Connection creation returned an empty response.", 201);
  return connection;
}

export async function updateConnection(
  connectionId: string,
  payload: DatabaseConnectionUpdate,
): Promise<DatabaseConnection> {
  const connection = await apiRequest<DatabaseConnection>(
    `/databases/connections/${encodeURIComponent(connectionId)}`,
    { method: "PATCH", body: payload },
  );
  if (!connection) throw new ApiClientError("Connection update returned an empty response.", 200);
  return connection;
}

export async function deleteConnection(connectionId: string): Promise<void> {
  await apiRequest(`/databases/connections/${encodeURIComponent(connectionId)}`, { method: "DELETE" });
}

export async function testConnection(connectionId: string): Promise<ConnectionValidationResult> {
  const result = await apiRequest<ConnectionValidationResult>(
    `/databases/connections/${encodeURIComponent(connectionId)}/test`,
    { method: "POST" },
  );
  if (!result) throw new ApiClientError("Connection test returned an empty response.", 200);
  return result;
}
