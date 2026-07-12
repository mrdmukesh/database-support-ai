import type { KnowledgeArticle, LearningDashboard } from "../models/learning";
import { apiRequest } from "./client";
function query(organizationId: string, workspaceId: string) { return new URLSearchParams({ organization_id: organizationId, workspace_id: workspaceId }).toString(); }
export async function loadLearningDashboard(organizationId: string, workspaceId: string, signal?: AbortSignal): Promise<LearningDashboard> {
  return (await apiRequest<LearningDashboard>(`/learning/dashboard?${query(organizationId, workspaceId)}`, { signal }))!;
}
export async function listKnowledge(organizationId: string, workspaceId: string, signal?: AbortSignal): Promise<KnowledgeArticle[]> {
  return (await apiRequest<KnowledgeArticle[]>(`/learning/knowledge?${query(organizationId, workspaceId)}`, { signal })) ?? [];
}
