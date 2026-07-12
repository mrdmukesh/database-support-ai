import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext, type AuthState } from "../../stores/auth-store";
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

const auth: AuthState = {
  session: null,
  user: { id: "user-1", organization_id: "ORG-1", email: "dba@example.com", full_name: "DBA", role: "dba", is_active: true },
  organizationId: "ORG-1",
  isAuthenticated: true,
  isInitializing: false,
  login: vi.fn(),
  logout: vi.fn(),
};

function RouteHarness() {
  const navigate = useNavigate();

  return (
    <>
      <button onClick={() => navigate("/app/investigations/INV-8")}>Go to INV-8</button>
      <Routes>
        <Route path="/app/investigations/:investigationId?" element={<InvestigationResultPage />} />
        <Route path="/missing-id" element={<InvestigationResultPage />} />
      </Routes>
    </>
  );
}

function renderRoute(path = "/app/investigations/INV-7") {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[path]}>
        <RouteHarness />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("InvestigationResultPage route and loading", () => {
  beforeEach(() => loadSavedInvestigation.mockReset());

  it("loads a valid ID and renders the current result containers", async () => {
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

  it.each([
    ["undefined ID", "/app/investigations"],
    ["empty ID", "/app/investigations/"],
    ["whitespace-only ID", "/app/investigations/%20%20"],
  ])("renders the not-found state for a %s", async (_label, path) => {
    renderRoute(path);

    expect(await screen.findByRole("heading", { name: "Investigation not found" })).toBeInTheDocument();
    expect(loadSavedInvestigation).not.toHaveBeenCalled();
  });

  it("shows an API failure state when loading the investigation fails", async () => {
    loadSavedInvestigation.mockRejectedValueOnce(new Error("Boom"));
    renderRoute();

    expect(await screen.findByRole("alert")).toHaveTextContent("Boom");
    expect(screen.getByRole("heading", { name: "Unable to load investigation" })).toBeInTheDocument();
  });

  it("ignores stale responses when the route ID changes", async () => {
    let resolveFirst!: (value: SavedInvestigation) => void;
    const firstRequest = new Promise<SavedInvestigation>((done) => { resolveFirst = done; });
    const secondRequest = Promise.resolve({ ...saved, id: "INV-8", user_question: "Why was the invoice rejected?" });
    loadSavedInvestigation
      .mockImplementationOnce(() => firstRequest)
      .mockImplementationOnce(() => secondRequest);

    renderRoute("/app/investigations/INV-7");
    expect(screen.getByRole("status")).toHaveTextContent("Loading investigation...");

    fireEvent.click(screen.getByRole("button", { name: "Go to INV-8" }));
    resolveFirst(saved);

    await waitFor(() => expect(loadSavedInvestigation).toHaveBeenCalledWith("INV-8", expect.any(AbortSignal)));
    expect(await screen.findByRole("heading", { name: "Investigation INV-8" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Investigation INV-7" })).not.toBeInTheDocument();
  });
});
