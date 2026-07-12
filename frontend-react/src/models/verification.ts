import type { ReportLinks } from "./report";

export interface VerificationCheck {
  id: string;
  investigation_id: string;
  claim: string;
  purpose: string;
  claim_being_verified: string;
  evidence_logic: string;
  expected_result_explanation: string;
  interpretation: string;
  conclusion_template: string;
  verification_sql: string;
  expected_result: string;
  risk_level: string;
  source: string;
  status: string;
  actual_result_summary: string;
  confidence_impact: string;
  notes: string;
  verified_by: string;
  verified_at: string | null;
}

export interface VerificationRunRequest {
  verification_sql?: string | null;
}

export interface VerificationRunAllResponse {
  checks: VerificationCheck[];
  report: ReportLinks | null;
}
