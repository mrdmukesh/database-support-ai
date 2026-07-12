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
}

export interface InvestigationSummary {
  id: string;
  organization_id: string;
  workspace_id: string;
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
