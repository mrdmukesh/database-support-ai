import type { VerificationCheck, VerificationRunAllResponse, VerificationRunRequest } from "../models/verification";
import { ApiClientError, apiRequest } from "./client";

export async function loadVerificationChecks(investigationId: string, signal?: AbortSignal): Promise<VerificationCheck[]> {
  return (await apiRequest<VerificationCheck[]>(`/chat/investigations/${encodeURIComponent(investigationId)}/verification-checks`, { signal })) ?? [];
}
export async function runVerificationCheck(checkId: string, request: VerificationRunRequest = {}): Promise<VerificationCheck> {
  const result = await apiRequest<VerificationCheck>(`/chat/verification-checks/${encodeURIComponent(checkId)}/run`, { method: "POST", body: request });
  if (!result) throw new ApiClientError("Verification returned an empty response.", 200);
  return result;
}
export async function skipVerificationCheck(checkId: string): Promise<VerificationCheck> {
  const result = await apiRequest<VerificationCheck>(`/chat/verification-checks/${encodeURIComponent(checkId)}/skip`, { method: "POST" });
  if (!result) throw new ApiClientError("Verification returned an empty response.", 200);
  return result;
}
export async function runAllVerificationChecks(investigationId: string): Promise<VerificationRunAllResponse> {
  const result = await apiRequest<VerificationRunAllResponse>(`/chat/investigations/${encodeURIComponent(investigationId)}/verification-checks/run-all`, { method: "POST" });
  if (!result) throw new ApiClientError("Verification returned an empty response.", 200);
  return result;
}
