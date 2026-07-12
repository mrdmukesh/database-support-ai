import { describe, expect, it } from "vitest";
import type { Session } from "./auth";
import type { InvestigationSubmitResponse, SavedInvestigation } from "./investigation";
import type { ReportLinks } from "./report";
import type { VerificationCheck } from "./verification";

const reportFixture: ReportLinks = {
  investigation_id: "INV-1",
  html: "/reports/INV-1/report.html",
  pdf: "/reports/INV-1/report.pdf",
};

describe("verified API model fixtures", () => {
  it("preserves the authenticated session contract", () => {
    const session = {
      access_token: "test-token",
      token_type: "bearer",
      user: {
        id: "USER-1",
        organization_id: "ORG-1",
        email: "admin@example.com",
        full_name: "Admin",
        role: "organization_admin",
        is_active: true,
      },
    } satisfies Session;

    expect(session.user.organization_id).toBe("ORG-1");
  });

  it("preserves nullable investigation and message fields", () => {
    const message = {
      id: "MSG-1",
      conversation_id: "CONV-1",
      role: "assistant",
      content: "Investigation result",
      confidence: null,
      source_count: 0,
      requires_human_review: true,
    };
    const response = {
      conversation: {
        id: "CONV-1",
        organization_id: "ORG-1",
        workspace_id: "WS-1",
        user_id: "USER-1",
        title: "Investigation",
      },
      user_message: { ...message, id: "MSG-0", role: "user" },
      assistant_message: message,
      findings: [],
      confidence: 0,
      requires_human_review: true,
      sources: [],
      report: null,
      investigation_id: null,
      connection_id: "DB-1",
      connection_name: "Primary DB",
    } satisfies InvestigationSubmitResponse;

    expect(response.report).toBeNull();
    expect(response.assistant_message.confidence).toBeNull();
  });

  it("accepts the legacy saved-investigation report shape", () => {
    const saved = {
      id: "INV-1",
      organization_id: "ORG-1",
      workspace_id: "WS-1",
      connection_id: "DB-1",
      connection_name: "Primary DB",
      user_question: "Why did it fail?",
      detected_intent: "production_investigation",
      ai_answer: "Answer",
      confidence_score: 0,
      report_path: "reports/history/INV-1",
      status: "AI_ANSWERED",
      created_at: "2026-07-11T00:00:00Z",
      report: reportFixture,
    } satisfies SavedInvestigation;

    expect(saved.report.xlsx).toBeUndefined();
  });

  it("preserves nullable verification timestamps", () => {
    const check = {
      id: "CHECK-1",
      investigation_id: "INV-1",
      claim: "Claim",
      purpose: "",
      claim_being_verified: "",
      evidence_logic: "",
      expected_result_explanation: "",
      interpretation: "",
      conclusion_template: "",
      verification_sql: "SELECT 1",
      expected_result: "One row",
      risk_level: "Read-only",
      source: "SQL",
      status: "Pending",
      actual_result_summary: "",
      confidence_impact: "",
      notes: "",
      verified_by: "",
      verified_at: null,
    } satisfies VerificationCheck;

    expect(check.verified_at).toBeNull();
  });
});
