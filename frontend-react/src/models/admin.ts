export interface CleanupCounts {
  connections: number;
  workspaces: number;
  investigations: number;
  evidence: number;
  execution_traces: number;
  planner_selections: number;
  agentic_steps: number;
  llm_invocation_audit: number;
  feedback: number;
  verification_checks: number;
}

export interface CleanupPreviewResponse {
  counts: Partial<CleanupCounts>;
  dependency_order?: string[];
  shared_workspace_ids_sample?: string[];
  zero_workspaces_supported?: boolean;
  one_default_workspace_required?: boolean;
}

export interface CleanupExecuteRequest {
  confirmation: string;
  keep_default_workspace: boolean;
}

export interface CleanupExecuteResponse {
  status: string;
  before?: Record<string, number>;
  after?: Record<string, number>;
  summary?: Record<string, number>;
  correlation_id?: string;
}
