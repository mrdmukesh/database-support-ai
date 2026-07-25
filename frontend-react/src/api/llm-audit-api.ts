import { apiRequest } from "./client";
import type { LLMInvocationDetail, LLMInvocationSummary, ZeroInvocationExplanation } from "../models/llm-audit";

export type AuditFilters = {
  investigation_id?: string;
  stage_name?: string;
  provider?: string;
  model?: string;
  status?: string;
  failed_only?: boolean;
  search?: string;
  started_after?: string;
  started_before?: string;
  page?: number;
  page_size?: number;
};

export async function listLLMInvocations(filters: AuditFilters = {}) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return apiRequest<{ items: LLMInvocationSummary[]; total: number; page: number; page_size: number; zero_invocation_explanation: ZeroInvocationExplanation | null }>(
    `/admin/llm-invocations?${query}`,
  );
}

export async function getLLMInvocation(id: string) {
  return apiRequest<LLMInvocationDetail>(`/admin/llm-invocations/${id}`);
}

export async function getInvestigationLLMActivity(investigationId: string) {
  return apiRequest<{ items: LLMInvocationSummary[]; captured: boolean; message: string | null; zero_invocation_explanation: ZeroInvocationExplanation | null }>(
    `/admin/investigations/${investigationId}/llm-invocations`,
  );
}
