import type { FeedbackReviewRequest, InvestigationFeedback, InvestigationFeedbackCreate } from "../models/feedback";
import { ApiClientError, apiRequest } from "./client";
export async function submitInvestigationFeedback(investigationId: string, payload: InvestigationFeedbackCreate): Promise<InvestigationFeedback> {
  const result = await apiRequest<InvestigationFeedback>(`/learning/investigations/${encodeURIComponent(investigationId)}/feedback`, { method: "POST", body: payload });
  if (!result) throw new ApiClientError("Feedback returned an empty response.", 201); return result;
}
export async function listFeedback(organizationId: string, workspaceId: string, statusFilter?: string, signal?: AbortSignal): Promise<InvestigationFeedback[]> {
  const query = new URLSearchParams({ organization_id: organizationId, workspace_id: workspaceId }); if (statusFilter) query.set("status_filter", statusFilter);
  return (await apiRequest<InvestigationFeedback[]>(`/learning/feedback?${query}`, { signal })) ?? [];
}
export async function reviewFeedback(feedbackId: string, payload: FeedbackReviewRequest): Promise<InvestigationFeedback> {
  const result = await apiRequest<InvestigationFeedback>(`/learning/feedback/${encodeURIComponent(feedbackId)}/review`, { method: "POST", body: payload });
  if (!result) throw new ApiClientError("Feedback review returned an empty response.", 200); return result;
}
