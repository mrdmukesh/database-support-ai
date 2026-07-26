export type LLMInvocationSummary = {
  llm_invocation_id: string;
  investigation_id: string | null;
  connection_id?: string | null;
  environment_type?: string;
  policy_name?: string;
  policy_version?: string;
  logical_request_id: string;
  stage_name: string;
  agent_name: string;
  provider: string;
  model_name: string;
  status: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  duration_ms: number | null;
  estimated_cost: number | null;
  currency: string;
  retry_attempt: number;
  started_at: string;
};

export type LLMInvocationDetail = LLMInvocationSummary & {
  system_prompt_sanitized: string;
  user_prompt_sanitized: string;
  context_payload_sanitized: string;
  tool_definitions_sanitized: string;
  response_text_sanitized: string;
  error_message_sanitized: string;
  request_payload_hash: string;
  response_payload_hash: string | null;
  finish_reason: string | null;
  correlation_id: string | null;
  trace_id: string | null;
  prompt_template_name: string | null;
  prompt_template_version: string | null;
  application_commit: string | null;
  redaction_notice: string;
};

export type ZeroInvocationExplanation = {
  code: string;
  reason: string;
};
