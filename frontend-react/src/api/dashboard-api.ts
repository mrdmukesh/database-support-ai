import { ApiClientError, apiRequest } from "./client";

export interface DashboardSummary {
  organizations: number;
  users: number;
  active_subscriptions: number;
  documents: number;
  incidents: number;
  [key: string]: unknown;
}

export interface ApiHealthComponent {
  name: string;
  status: string;
  detail: unknown;
}

export interface ApiHealth {
  status: string;
  components: ApiHealthComponent[];
  [key: string]: unknown;
}

export interface DisclaimerResponse {
  disclaimer: string[];
}

export async function getDashboardSummary(signal?: AbortSignal): Promise<DashboardSummary> {
  const summary = await apiRequest<DashboardSummary>("/admin/summary", { signal });
  if (!summary) throw new ApiClientError("Dashboard summary returned an empty response.", 200);
  return summary;
}

export async function getApiHealth(signal?: AbortSignal): Promise<ApiHealth> {
  const health = await apiRequest<ApiHealth>("/health", { signal });
  if (!health) throw new ApiClientError("API health returned an empty response.", 200);
  return health;
}

export async function getDisclaimer(signal?: AbortSignal): Promise<string[]> {
  const response = await apiRequest<DisclaimerResponse>("/ai/disclaimer", { signal });
  return response?.disclaimer ?? [];
}
