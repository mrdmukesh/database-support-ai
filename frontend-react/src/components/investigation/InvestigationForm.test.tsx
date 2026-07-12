import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InvestigationProvider } from "../../features/investigation/investigation-context";
import type { InvestigationSubmitResponse } from "../../models/investigation";
import { AuthContext, type AuthState } from "../../stores/auth-store";
import { InvestigationForm } from "./InvestigationForm";

const submitInvestigation = vi.fn();
vi.mock("../../api/investigation-api", () => ({
  submitInvestigation: (...args: unknown[]) => submitInvestigation(...args),
}));

const workspaces = [
  { id: "workspace-1", organization_id: "org-1", name: "Finance", slug: "finance", is_active: true },
  { id: "workspace-2", organization_id: "org-1", name: "Operations", slug: "ops", is_active: true },
];
const connections = [
  { id: "connection-1", organization_id: "org-1", workspace_id: "workspace-1", engine: "sqlserver", name: "Finance DB", is_active: true },
  { id: "connection-2", organization_id: "org-1", workspace_id: "workspace-2", engine: "postgresql", name: "Operations DB", is_active: true },
];
const response = {
  conversation: { id: "conversation-1", organization_id: "org-1", workspace_id: "workspace-1", user_id: "user-1", title: "Question" },
  user_message: { id: "user-message", conversation_id: "conversation-1", role: "user", content: "Question", confidence: null, source_count: 0, requires_human_review: false },
  assistant_message: { id: "assistant-message", conversation_id: "conversation-1", role: "assistant", content: "Answer", confidence: 0.8, source_count: 1, requires_human_review: false },
  findings: [], confidence: 0.8, requires_human_review: false, sources: ["SQL-1"], report: null, investigation_id: "investigation-1",
} satisfies InvestigationSubmitResponse;

const auth: AuthState = {
  session: null,
  user: { id: "user-1", organization_id: "org-1", email: "dba@example.com", role: "dba", is_active: true },
  organizationId: "org-1",
  isAuthenticated: true,
  login: vi.fn(),
  logout: vi.fn(),
};

function Providers({ children }: { children: ReactNode }) {
  return <AuthContext.Provider value={auth}><InvestigationProvider>{children}</InvestigationProvider></AuthContext.Provider>;
}

function renderForm() {
  return render(<InvestigationForm workspaces={workspaces} connections={connections} />, { wrapper: Providers });
}

function fillForm() {
  fireEvent.change(screen.getByLabelText("Workspace"), { target: { value: "workspace-1" } });
  fireEvent.change(screen.getByLabelText("Database connection"), { target: { value: "connection-1" } });
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "  Why is payment duplicated?  " } });
}

describe("InvestigationForm", () => {
  beforeEach(() => submitInvestigation.mockReset());

  it("filters connections by the selected workspace", () => {
    renderForm();
    expect(screen.getByLabelText("Database connection")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Workspace"), { target: { value: "workspace-1" } });
    expect(screen.getByRole("option", { name: "Finance DB" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Operations DB" })).not.toBeInTheDocument();
  });

  it("validates each required field before submission", () => {
    renderForm();
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Select a workspace.");
    fireEvent.change(screen.getByLabelText("Workspace"), { target: { value: "workspace-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Select a database connection.");
    fireEvent.change(screen.getByLabelText("Database connection"), { target: { value: "connection-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter an investigation question.");
    expect(submitInvestigation).not.toHaveBeenCalled();
  });

  it("submits the verified payload and completes successfully", async () => {
    submitInvestigation.mockResolvedValue(response);
    renderForm();
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(screen.getByRole("button", { name: "Analyzing..." })).toBeDisabled();
    await waitFor(() => expect(submitInvestigation).toHaveBeenCalledWith({
      organization_id: "org-1",
      workspace_id: "workspace-1",
      user_id: "user-1",
      question: "Why is payment duplicated?",
    }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled());
  });

  it("shows API failures and restores the enabled form", async () => {
    submitInvestigation.mockRejectedValue(new Error("Evidence collection failed."));
    renderForm();
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Evidence collection failed.");
    expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled();
  });
});
