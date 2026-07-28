import type { ReportLinks } from "./report";

export interface ChatConversation {
  id: string;
  organization_id: string;
  workspace_id: string;
  user_id: string;
  title: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  confidence: number | null;
  source_count: number;
  requires_human_review: boolean;
}

export interface InvestigationSubmitRequest {
  organization_id: string;
  workspace_id: string;
  connection_id: string;
  environment_type: string;
  user_id: string;
  question: string;
  conversation_id?: string | null;
}

export interface InvestigationSubmitResponse {
  conversation: ChatConversation;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  findings: string[];
  confidence: number;
  requires_human_review: boolean;
  sources: string[];
  report: ReportLinks | null;
  investigation_id: string | null;
  connection_id: string;
  connection_name: string;
  environment_type?: string;
  policy_name?: string;
  policy_version?: string;
}

export interface InvestigationSummary {
  id: string;
  organization_id: string;
  workspace_id: string;
  connection_id: string;
  connection_name: string;
  environment_type?: string;
  policy_name?: string;
  policy_version?: string;
  policy_audit_json?: string;
  user_question: string;
  detected_intent: string;
  ai_answer: string;
  confidence_score: number | null;
  report_path: string;
  status: string;
  created_at: string;
}

/** Route-compatible detail shape; this backend route does not declare a response model. */
export interface SavedInvestigation extends Omit<InvestigationSummary, "confidence_score"> {
  confidence_score: number;
  report: ReportLinks;
  [key: string]: unknown;
}

export interface ProgressEvidence {
  evidence_id: string;
  purpose: string;
  execution_status: string;
  evidence_semantics: string;
  row_count: number;
  supports_claim: string;
}

export interface InvestigationProgressStep {
  iteration: number;
  state: string;
  action: string;
  reason: string;
  result: string;
  created_evidence: ProgressEvidence[];
  created_at: string;
}

export interface InvestigationProgress {
  investigation_id: string;
  agentic: boolean;
  current_state: string;
  iteration_number: number;
  terminal: boolean;
  stop_reason: string;
  budget: Record<string, number>;
  resolved_entities: Array<{
    entity_type: string;
    value: string;
    status: string;
    confidence?: number | null;
    evidence_refs: string[];
  }>;
  question_counts: Record<"open" | "answered" | "partial" | "blocked", number>;
  questions: Array<Record<string, unknown>>;
  completed_steps: InvestigationProgressStep[];
  failed_actions: InvestigationProgressStep[];
  verified_absence: ProgressEvidence[];
  root_cause_status: string;
  fix_readiness_state: string;
  source_badges: string[];
  can_cancel: boolean;
}
