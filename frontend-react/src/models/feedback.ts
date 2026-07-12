export type FeedbackRating =
  | "HELPFUL"
  | "NOT_HELPFUL"
  | "PARTIALLY_CORRECT"
  | "WRONG_ROOT_CAUSE"
  | "MISSING_EVIDENCE"
  | "NEEDS_DBA_REVIEW";

export interface InvestigationFeedbackCreate {
  rating: FeedbackRating;
  actual_root_cause?: string;
  actual_fix_applied?: string;
  sql_or_procedure_changed?: string;
  test_cases_executed?: string;
  proof_of_fix?: string;
  rollback_used?: string;
  production_issue_resolved?: boolean | null;
  notes?: string;
}

export interface InvestigationFeedback {
  id: string;
  organization_id: string;
  workspace_id: string;
  investigation_id: string;
  rating: string;
  actual_root_cause: string;
  actual_fix_applied: string;
  sql_or_procedure_changed: string;
  test_cases_executed: string;
  proof_of_fix: string;
  rollback_used: string;
  production_issue_resolved: boolean | null;
  notes: string;
  status: string;
  review_notes: string;
  created_at: string;
}

export interface FeedbackReviewRequest {
  approved: boolean;
  review_notes?: string;
  title?: string | null;
  module_name?: string;
  issue_type?: string;
  severity?: string;
  rollback_plan?: string;
  confidence_after_approval?: number;
}
