import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SavedInvestigation } from "../../models/investigation";
import { InvestigationResultPage } from "./InvestigationResultPage";

const loadSavedInvestigation = vi.fn();
vi.mock("../../api/investigation-api", () => ({
  loadSavedInvestigation: (...args: unknown[]) => loadSavedInvestigation(...args),
}));

const saved: SavedInvestigation = {
  id: "INV-7",
  organization_id: "ORG-1",
  workspace_id: "WS-1",
  user_question: "Why was payment duplicated?",
  detected_intent: "duplicate_data",
  ai_answer: "## Confirmed Facts\n- SQL-1 returned two rows.",
  confidence_score: 0,
  report_path: "reports/INV-7",
  status: "AI_ANSWERED",
  created_at: "2026-07-12T00:00:00Z",
  report: { investigation_id: "INV-7", html: "/report.html", pdf: "/report.pdf" },
};

function renderRoute(path = "/app/investigations/INV-7") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/investigations/:investigationId" element={<InvestigationResultPage />} />
        <Route path="/missing-id" element={<InvestigationResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("InvestigationResultPage route and loading", () => {
  beforeEach(() => loadSavedInvestigation.mockReset());

  it("accepts the route ID, shows loading, and renders current result containers", async () => {
    let resolve!: (value: SavedInvestigation) => void;
    loadSavedInvestigation.mockReturnValue(new Promise((done) => { resolve = done; }));
    renderRoute();
    expect(screen.getByRole("status")).toHaveTextContent("Loading investigation...");
    expect(loadSavedInvestigation).toHaveBeenCalledWith("INV-7", expect.any(AbortSignal));

    resolve(saved);
    expect(await screen.findByRole("heading", { name: "Investigation INV-7" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Executive Summary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Most Likely Root Cause" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Confirmed Evidence" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recommended Next Step" })).toBeInTheDocument();
    expect(screen.getByText("Confidence 0%")).toBeInTheDocument();
  });

  it("shows not found when the route has no investigation ID", async () => {
    renderRoute("/missing-id");
    expect(await screen.findByRole("heading", { name: "Investigation not found" })).toBeInTheDocument();
    expect(loadSavedInvestigation).not.toHaveBeenCalled();
  });

});
