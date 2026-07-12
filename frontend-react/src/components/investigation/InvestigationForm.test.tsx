import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../api/client";
import { submitInvestigation } from "../../api/investigation-api";
import { InvestigationProvider } from "../../features/investigation/investigation-context";
import type { InvestigationSubmitResponse } from "../../models/investigation";
import { AuthContext, type AuthState } from "../../stores/auth-store";
import { InvestigationForm } from "./InvestigationForm";

vi.mock("../../api/investigation-api", () => ({
  submitInvestigation: vi.fn(),
}));

const mockedSubmitInvestigation = vi.mocked(submitInvestigation);

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
  user: { id: "user-1", organization_id: "org-1", email: "dba@example.com", full_name: "DBA", role: "dba", is_active: true },
  organizationId: "org-1",
  isAuthenticated: true,  isInitializing: false,  login: vi.fn(),
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
  beforeEach(() => mockedSubmitInvestigation.mockReset());

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
    expect(mockedSubmitInvestigation).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled();
  });

  it("submits the verified payload and completes successfully", async () => {
    mockedSubmitInvestigation.mockResolvedValue(response);
    renderForm();
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(screen.getByRole("button", { name: "Analyzing..." })).toBeDisabled();
    await waitFor(() => expect(mockedSubmitInvestigation).toHaveBeenCalledWith({
      organization_id: "org-1",
      workspace_id: "workspace-1",
      user_id: "user-1",
      question: "Why is payment duplicated?",
    }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled());
  });

  it("shows rejected API errors and restores the enabled form", async () => {
    mockedSubmitInvestigation.mockRejectedValueOnce(new Error("Evidence collection failed."));
    renderForm();
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Evidence collection failed.");
    expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled();
  });

  it("shows normalized server errors from the API client", async () => {
    mockedSubmitInvestigation.mockRejectedValueOnce(new ApiClientError("Report generation failed", 500, { detail: "Report generation failed" }));
    renderForm();
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Report generation failed");
    expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled();
  });

  it("shows network errors without disabling the form permanently", async () => {
    mockedSubmitInvestigation.mockRejectedValueOnce(new ApiClientError("Network request failed.", 0));
    renderForm();
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Network request failed.");
    expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled();
  });

  it("preserves the entered question and selections after a failed submission", async () => {
    mockedSubmitInvestigation.mockRejectedValueOnce(new Error("Evidence collection failed."));
    renderForm();
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Ask AI" })).toBeEnabled());
    expect(screen.getByLabelText("Workspace")).toHaveValue("workspace-1");
    expect(screen.getByLabelText("Database connection")).toHaveValue("connection-1");
    expect(screen.getByLabelText("Question")).toHaveValue("  Why is payment duplicated?  ");
  });
});
