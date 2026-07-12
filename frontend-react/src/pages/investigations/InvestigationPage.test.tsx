import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InvestigationSubmitResponse } from "../../models/investigation";
import { AuthContext, type AuthState } from "../../stores/auth-store";
import { InvestigationPage } from "./InvestigationPage";

const listWorkspaces = vi.fn();
const listConnections = vi.fn();
const submitInvestigation = vi.fn();

vi.mock("../../api/workspace-api", () => ({
  listWorkspaces: (...args: unknown[]) => listWorkspaces(...args),
}));
vi.mock("../../api/connection-api", () => ({
  listConnections: (...args: unknown[]) => listConnections(...args),
}));
vi.mock("../../api/investigation-api", () => ({
  submitInvestigation: (...args: unknown[]) => submitInvestigation(...args),
}));

const workspaces = [
  { id: "workspace-1", organization_id: "org-1", name: "Finance", slug: "finance", is_active: true },
];
const connections = [
  { id: "connection-1", organization_id: "org-1", workspace_id: "workspace-1", engine: "sqlserver", name: "Finance DB", is_active: true },
];
const baseResponse: InvestigationSubmitResponse = {
  conversation: { id: "conversation-1", organization_id: "org-1", workspace_id: "workspace-1", user_id: "user-1", title: "Question" },
  user_message: { id: "user-message", conversation_id: "conversation-1", role: "user", content: "Question", confidence: null, source_count: 0, requires_human_review: false },
  assistant_message: { id: "assistant-message", conversation_id: "conversation-1", role: "assistant", content: "Partial evidence-backed answer", confidence: 0.6, source_count: 1, requires_human_review: true },
  findings: [], confidence: 0.6, requires_human_review: true, sources: ["SQL-1"], report: null,
  investigation_id: "INV-1",
};
const auth: AuthState = {
  session: null,
  user: { id: "user-1", organization_id: "org-1", email: "dba@example.com", role: "dba", is_active: true },
  organizationId: "org-1", isAuthenticated: true, login: vi.fn(), logout: vi.fn(),
};

function renderPage() {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={["/app/investigations"]}>
        <Routes>
          <Route path="/app/investigations" element={<InvestigationPage />} />
          <Route path="/app/investigations/:investigationId" element={<p>Result route</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

async function fillAndSubmit() {
  await screen.findByRole("button", { name: "Ask AI" });
  fireEvent.change(screen.getByLabelText("Workspace"), { target: { value: "workspace-1" } });
  fireEvent.change(screen.getByLabelText("Database connection"), { target: { value: "connection-1" } });
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Why duplicate?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));
}

describe("InvestigationPage orchestration", () => {
  beforeEach(() => {
    listWorkspaces.mockReset().mockResolvedValue(workspaces);
    listConnections.mockReset().mockResolvedValue(connections);
    submitInvestigation.mockReset();
  });

  it("loads form options through services and displays the unchanged form", async () => {
    renderPage();
    expect(screen.getByRole("status")).toHaveTextContent("Loading investigation options...");
    expect(await screen.findByRole("button", { name: "Ask AI" })).toBeEnabled();
    expect(listWorkspaces).toHaveBeenCalledWith("org-1", expect.any(AbortSignal));
    expect(listConnections).toHaveBeenCalledWith("org-1", undefined, expect.any(AbortSignal));
  });

  it("shows setup service errors without rendering the form", async () => {
    listWorkspaces.mockRejectedValue(new Error("Workspace service unavailable."));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Workspace service unavailable.");
    expect(screen.queryByRole("button", { name: "Ask AI" })).not.toBeInTheDocument();
  });

  it("shows submission loading and errors", async () => {
    submitInvestigation.mockRejectedValue(new Error("Evidence collection failed."));
    renderPage();
    await fillAndSubmit();
    expect(screen.getByRole("button", { name: "Analyzing..." })).toBeDisabled();
    expect(await screen.findByRole("alert")).toHaveTextContent("Evidence collection failed.");
    expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled();
  });

  it("navigates after a valid investigation ID is returned", async () => {
    submitInvestigation.mockResolvedValue(baseResponse);
    renderPage();
    await fillAndSubmit();
    expect(await screen.findByText("Result route")).toBeInTheDocument();
  });

  it("preserves partial API success inline when no investigation ID is returned", async () => {
    submitInvestigation.mockResolvedValue({ ...baseResponse, investigation_id: null });
    renderPage();
    await fillAndSubmit();
    expect(await screen.findByRole("heading", { name: "Investigation result" })).toBeInTheDocument();
    expect(screen.getByText("Partial evidence-backed answer")).toBeInTheDocument();
    expect(screen.queryByText("Result route")).not.toBeInTheDocument();
  });

  it("treats a blank investigation ID as partial success instead of navigating", async () => {
    submitInvestigation.mockResolvedValue({ ...baseResponse, investigation_id: "   " });
    renderPage();
    await fillAndSubmit();
    await waitFor(() => expect(screen.getByText("Partial evidence-backed answer")).toBeInTheDocument());
    expect(screen.queryByText("Result route")).not.toBeInTheDocument();
  });
});
