import type {
  ChatConversation,
  ChatMessage,
  InvestigationSubmitRequest,
  InvestigationSubmitResponse,
  InvestigationSummary,
  SavedInvestigation,
} from "../models/investigation";
import { ApiClientError, apiRequest } from "./client";

export interface InvestigationScope {
  organizationId: string;
  workspaceId: string;
  userId: string;
}

function conversationQuery(scope: InvestigationScope): string {
  return new URLSearchParams({
    organization_id: scope.organizationId,
    workspace_id: scope.workspaceId,
    user_id: scope.userId,
  }).toString();
}

export async function submitInvestigation(
  payload: InvestigationSubmitRequest,
  signal?: AbortSignal,
): Promise<InvestigationSubmitResponse> {
  const response = await apiRequest<InvestigationSubmitResponse>("/chat/ask", {
    method: "POST",
    body: payload,
    signal,
  });
  if (!response) throw new ApiClientError("Investigation returned an empty response.", 201);
  return response;
}

export async function loadConversations(
  scope: InvestigationScope,
  signal?: AbortSignal,
): Promise<ChatConversation[]> {
  return (
    (await apiRequest<ChatConversation[]>(`/chat/conversations?${conversationQuery(scope)}`, {
      signal,
    })) ?? []
  );
}

export async function loadConversationMessages(
  conversationId: string,
  scope: InvestigationScope,
  signal?: AbortSignal,
): Promise<ChatMessage[]> {
  return (
    (await apiRequest<ChatMessage[]>(
      `/chat/conversations/${encodeURIComponent(conversationId)}/messages?${conversationQuery(scope)}`,
      { signal },
    )) ?? []
  );
}

export async function loadInvestigationHistory(
  organizationId: string,
  workspaceId: string,
  statusFilter?: string,
  signal?: AbortSignal,
): Promise<InvestigationSummary[]> {
  const query = new URLSearchParams({
    organization_id: organizationId,
    workspace_id: workspaceId,
  });
  if (statusFilter) query.set("status_filter", statusFilter);
  return (await apiRequest<InvestigationSummary[]>(`/learning/investigations?${query}`, { signal })) ?? [];
}

export async function loadSavedInvestigation(
  investigationId: string,
  signal?: AbortSignal,
): Promise<SavedInvestigation> {
  const response = await apiRequest<SavedInvestigation>(
    `/learning/investigations/${encodeURIComponent(investigationId)}`,
    { signal },
  );
  if (!response) throw new ApiClientError("Saved investigation returned an empty response.", 200);
  return response;
}

/** Metadata is supplied by the same verified saved-investigation detail contract. */
export async function loadInvestigationMetadata(
  investigationId: string,
  signal?: AbortSignal,
): Promise<SavedInvestigation> {
  return loadSavedInvestigation(investigationId, signal);
}
