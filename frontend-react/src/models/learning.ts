import type { InvestigationSummary } from "./investigation";

export interface LearningDashboard {
  open_investigations: number;
  pending_feedback: number;
  pending_approval: number;
  approved_knowledge: number;
  reminders: InvestigationSummary[];
}

export interface KnowledgeArticle {
  id: string;
  workspace_id: string;
  title: string;
  module_name: string;
  issue_type: string;
  symptoms: string;
  actual_root_cause: string;
  fix_summary: string;
  test_cases: string;
  proof_of_fix: string;
  severity: string;
  confidence_after_approval: number | null;
  source_investigation_id: string | null;
  version: number;
  is_active: boolean;
  approved_at: string | null;
}
