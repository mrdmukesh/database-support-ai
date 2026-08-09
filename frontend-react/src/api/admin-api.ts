import type { CleanupPreviewResponse, CleanupExecuteRequest, CleanupExecuteResponse } from "../models/admin";
import { apiRequest } from "./client";

export async function previewCleanup(organizationId: string, signal?: AbortSignal): Promise<CleanupPreviewResponse> {
  const query = new URLSearchParams({ organization_id: organizationId });
  return (await apiRequest<CleanupPreviewResponse>(`/admin/test-data-cleanup/preview?${query}`, { method: "POST", signal }))!;
}

export async function executeCleanup(organizationId: string, body: CleanupExecuteRequest): Promise<CleanupExecuteResponse> {
  const query = new URLSearchParams({ organization_id: organizationId });
  return (await apiRequest<CleanupExecuteResponse>(`/admin/test-data-cleanup/execute?${query}`, { method: "POST", body }))!;
}
