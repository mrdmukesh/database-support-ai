import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBadge, EvidenceTable, InvestigationProgress, RiskBadge, SqlCodeBlock, StatusBadge } from ".";

describe("enterprise investigation UI components", () => {
  it("renders internal enums as user-friendly status labels", () => {
    render(<StatusBadge status="AI_ANSWERED" />);
    expect(screen.getByText("Ai Answered")).toBeInTheDocument();
  });

  it("renders confidence and risk indicators", () => {
    render(<><ConfidenceBadge confidence={0.82} /><RiskBadge risk="HIGH_RISK" /></>);
    expect(screen.getByText("Confidence 82%"));
    expect(screen.getByText("High Risk"));
  });

  it("exposes completed, active, pending, and failed progress states", () => {
    const { container } = render(<InvestigationProgress stages={[
      { label: "Validation", state: "completed" }, { label: "Discovery", state: "active" },
      { label: "Evidence", state: "pending" }, { label: "Report", state: "failed" },
    ]} />);
    expect(container.querySelectorAll("[data-state]")).toHaveLength(4);
    expect(screen.getByText("Discovery")).toBeInTheDocument();
  });

  it("renders structured evidence and read-only SQL", () => {
    render(<><EvidenceTable rows={[{ id: "SQL-1", source: "payments", finding: "Duplicate rows", state: "passed", contribution: "+20%" }]} /><SqlCodeBlock sql="SELECT * FROM payments" /></>);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Duplicate rows")).toBeInTheDocument();
    expect(screen.getByText("SELECT * FROM payments")).toBeInTheDocument();
    expect(screen.getByText("Read only")).toBeInTheDocument();
  });
});
