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
  sort_by?: string;
  sort_direction?: "asc" | "desc";
};

export type AuditPage = {
  items: LLMInvocationSummary[]; total: number; total_items: number; page: number; page_size: number;
  total_pages: number; has_previous: boolean; has_next: boolean;
  zero_invocation_explanation: ZeroInvocationExplanation | null;
};

export async function listLLMInvocations(filters: AuditFilters = {}, signal?: AbortSignal) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return apiRequest<AuditPage>(
    `/admin/llm-invocations?${query}`, { signal },
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
