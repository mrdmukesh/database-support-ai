import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { VerificationCheck } from "../../models/verification";
import { VerificationCheckCard } from "./VerificationCheckCard";
import { VerificationPanel } from "./VerificationPanel";
const load = vi.fn(), run = vi.fn(), skip = vi.fn(), runAll = vi.fn();
vi.mock("../../api/verification-api", () => ({
  loadVerificationChecks: (...a: unknown[]) => load(...a), runVerificationCheck: (...a: unknown[]) => run(...a),
  skipVerificationCheck: (...a: unknown[]) => skip(...a), runAllVerificationChecks: (...a: unknown[]) => runAll(...a),
}));
const check: VerificationCheck = { id: "C1", investigation_id: "I1", claim: "Rows still duplicate", purpose: "Confirm live condition", claim_being_verified: "Duplicates exist", evidence_logic: "", expected_result_explanation: "", interpretation: "", conclusion_template: "", verification_sql: "SELECT id FROM payments", expected_result: "Rows returned", risk_level: "Read only", source: "SQL-1", status: "Pending", actual_result_summary: "2 rows returned", confidence_impact: "May increase confidence", notes: "Read-only validation", verified_by: "", verified_at: null };
describe("verification components", () => {
  beforeEach(() => { load.mockReset().mockResolvedValue([check]); run.mockReset().mockResolvedValue({ ...check, status: "Passed" }); skip.mockReset().mockResolvedValue({ ...check, status: "Skipped" }); runAll.mockReset().mockResolvedValue({ checks: [{ ...check, status: "Passed" }], report: null }); });
  it("displays claim, purpose, read-only SQL and actual backend result without inferring success", () => { render(<VerificationCheckCard check={check} onRun={vi.fn()} onSkip={vi.fn()} />); expect(screen.getByText("Rows still duplicate")).toBeInTheDocument(); expect(screen.getByText(/Confirm live condition/)).toBeInTheDocument(); expect(screen.getByText("SELECT id FROM payments")).toBeInTheDocument(); expect(screen.queryByRole("textbox")).not.toBeInTheDocument(); expect(screen.getByText("2 rows returned")).toBeInTheDocument(); expect(screen.getByText("May increase confidence")).toBeInTheDocument(); });
  it("runs and skips supported pending actions by ID only", () => { const onRun=vi.fn(), onSkip=vi.fn(); render(<VerificationCheckCard check={check} onRun={onRun} onSkip={onSkip} />); fireEvent.click(screen.getByRole("button", { name: "Run check" })); fireEvent.click(screen.getByRole("button", { name: "Skip" })); expect(onRun).toHaveBeenCalledWith("C1"); expect(onSkip).toHaveBeenCalledWith("C1"); });
  it("loads the panel and supports run-all", async () => { render(<VerificationPanel investigationId="I1" />); expect(screen.getByRole("status")).toHaveTextContent("Loading verification checks"); const button=await screen.findByRole("button", { name: "Run all pending safe checks" }); fireEvent.click(button); expect(runAll).toHaveBeenCalledWith("I1"); });
  it("preserves missing investigation and empty check states", async () => { const { rerender }=render(<VerificationPanel investigationId={null} />); expect(screen.getByText("Generate an investigation to see verification checks.")).toBeInTheDocument(); load.mockResolvedValue([]); rerender(<VerificationPanel investigationId="I2" />); expect(await screen.findByText("No verification checks were suggested.")).toBeInTheDocument(); });
});
