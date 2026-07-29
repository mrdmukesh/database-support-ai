import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InvestigationProgress } from "../../models/investigation";
import { InvestigationProgressPanel } from "./InvestigationProgressPanel";

const loadProgress = vi.fn();
const cancelInvestigation = vi.fn();
vi.mock("../../api/investigation-api", () => ({
  loadInvestigationProgress: (...args: unknown[]) => loadProgress(...args),
  cancelAgenticInvestigation: (...args: unknown[]) => cancelInvestigation(...args),
}));

function progress(overrides: Partial<InvestigationProgress> = {}): InvestigationProgress {
  return {
    investigation_id: "INV-9",
    agentic: true,
    current_state: "EVIDENCE_ASSESSMENT",
    iteration_number: 2,
    terminal: false,
    stop_reason: "",
    budget: {
      iterations: 2,
      sql_queries: 3,
      total_rows: 18,
      execution_seconds: 4,
      llm_calls: 1,
    },
    resolved_entities: [{
      entity_type: "PAYROLL_ITEM",
      value: "PAY-42",
      status: "exact",
      confidence: 1,
      evidence_refs: ["E-1"],
    }],
    question_counts: { open: 2, answered: 3, partial: 1, blocked: 0 },
    questions: [],
    completed_steps: [{
      iteration: 1,
      state: "STATE_UPDATE",
      action: "STATUS_HISTORY",
      reason: "Highest-value unresolved question.",
      result: "SUCCEEDED",
      created_evidence: [{
        evidence_id: "E-1",
        purpose: "Payroll history",
        execution_status: "succeeded",
        evidence_semantics: "verified_rows",
        row_count: 2,
        supports_claim: "Payroll header exists.",
      }],
      created_at: "2026-07-27T10:00:00Z",
    }],
    failed_actions: [],
    verified_absence: [],
    root_cause_status: "CANDIDATE",
    fix_readiness_state: "INVESTIGATION_INCOMPLETE",
    source_badges: ["Deterministic Evidence", "Evidence Gap"],
    can_cancel: true,
    ...overrides,
  };
}

describe("InvestigationProgressPanel", () => {
  beforeEach(() => {
    loadProgress.mockReset();
    cancelInvestigation.mockReset().mockResolvedValue(undefined);
  });

  it("shows active state, budgets, entities, questions, timeline, and cancel", async () => {
    loadProgress.mockResolvedValue(progress());
    render(<InvestigationProgressPanel investigationId="INV-9" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(await screen.findByRole("heading", { name: "Investigation progress" })).toBeInTheDocument();
    expect(screen.getByText("PAY-42")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText(/Status History/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel investigation" })).toBeEnabled();
  });

  it("supports keyboard-operable evidence disclosure with aria-expanded", async () => {
    loadProgress.mockResolvedValue(progress());
    render(<InvestigationProgressPanel investigationId="INV-9" />);
    const disclosure = await screen.findByRole("button", { name: "Show evidence (1)" });

    expect(disclosure).toHaveAttribute("aria-expanded", "false");
    fireEvent.keyDown(disclosure, { key: "Enter" });
    fireEvent.click(disclosure);
    expect(disclosure).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Payroll history")).toBeInTheDocument();
  });

  it("shows terminal state and stop reason without cancel", async () => {
    loadProgress.mockResolvedValue(progress({
      current_state: "ROOT_CAUSE_CONFIRMED",
      terminal: true,
      stop_reason: "Every causal prerequisite is verified.",
      can_cancel: false,
      root_cause_status: "CONFIRMED",
      fix_readiness_state: "FIX_PROPOSAL_READY",
    }));
    render(<InvestigationProgressPanel investigationId="INV-9" />);

    expect(await screen.findByText("Every causal prerequisite is verified.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel investigation" })).not.toBeInTheDocument();
    expect(screen.getByText(/Fix Proposal Ready/i)).toBeInTheDocument();
  });

  it("separates blocked or failed actions from verified absence", async () => {
    const failed = { ...progress().completed_steps[0], result: "BLOCKED" };
    loadProgress.mockResolvedValue(progress({
      current_state: "POLICY_BLOCKED",
      terminal: true,
      stop_reason: "Production policy blocked the action.",
      failed_actions: [failed],
      verified_absence: [{
        evidence_id: "E-0",
        purpose: "Missing child",
        execution_status: "succeeded",
        evidence_semantics: "verified_absence",
        row_count: 0,
        supports_claim: "No child exists in scope.",
      }],
      can_cancel: false,
    }));
    render(<InvestigationProgressPanel investigationId="INV-9" />);

    expect(await screen.findByText("Failed or blocked actions")).toBeInTheDocument();
    expect(screen.getByText("Execution failure is not absence evidence.")).toBeInTheDocument();
    expect(screen.getByText("Successful zero-row checks for a defined scope.")).toBeInTheDocument();
  });

  it("shows budget exhaustion and empty data safely", async () => {
    loadProgress.mockResolvedValue(progress({
      current_state: "QUERY_BUDGET_EXHAUSTED",
      terminal: true,
      stop_reason: "SQL query budget exhausted at 16/16.",
      budget: { iterations: 8, sql_queries: 16, total_rows: 0, execution_seconds: 9, llm_calls: 0 },
      resolved_entities: [],
      question_counts: { open: 0, answered: 0, partial: 0, blocked: 0 },
      completed_steps: [],
      can_cancel: false,
    }));
    render(<InvestigationProgressPanel investigationId="INV-9" />);

    expect(await screen.findByText("SQL query budget exhausted at 16/16.")).toBeInTheDocument();
    expect(screen.getByText("No exact affected entity was recorded.")).toBeInTheDocument();
    expect(screen.getByText("No agentic investigation step has completed yet.")).toBeInTheDocument();
  });

  it("provides a backward-compatible older-investigation state", async () => {
    loadProgress.mockResolvedValue(progress({
      agentic: false,
      current_state: "AI_ANSWERED",
      source_badges: ["Deterministic Fallback"],
      can_cancel: false,
    }));
    render(<InvestigationProgressPanel investigationId="OLD-1" />);

    expect(await screen.findByRole("heading", { name: "Progress timeline not recorded" })).toBeInTheDocument();
    expect(screen.getByText(/existing report remains available/i)).toBeInTheDocument();
  });

  it("renders an accessible error with retry and refreshes after cancel", async () => {
    loadProgress.mockRejectedValueOnce(new Error("Progress unavailable"));
    const view = render(<InvestigationProgressPanel investigationId="INV-9" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Progress unavailable");

    loadProgress.mockResolvedValueOnce(progress());
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByRole("button", { name: "Cancel investigation" });
    loadProgress.mockResolvedValueOnce(progress({ terminal: true, can_cancel: false }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel investigation" }));
    await waitFor(() => expect(cancelInvestigation).toHaveBeenCalledWith("INV-9"));
    expect(loadProgress).toHaveBeenCalledTimes(3);
    view.unmount();
  });
});
