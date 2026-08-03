import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, vi, expect, beforeEach } from "vitest";
import { AuthContext, type AuthState } from "../../stores/auth-store";
import ResetTestData from "./ResetTestData";
import { ApiClientError } from "../../api/client";

vi.mock("../../api/admin-api", () => ({
  previewCleanup: vi.fn().mockResolvedValue({ counts: { connections: 1, workspaces: 1, investigations: 1, evidence: 1, execution_traces: 1, planner_selections: 1, agentic_steps: 1, llm_invocation_audit: 1, feedback: 1, verification_checks: 1 }, one_default_workspace_required: false }),
  executeCleanup: vi.fn().mockResolvedValue({ status: "ok", correlation_id: "corr-1", summary: { connections_deleted: 1 } }),
}));

const api = await import("../../api/admin-api");

function auth(role = "organization_admin"): AuthState {
  return {
    session: null,
    user: { id: "u", organization_id: "org", email: "a@b", full_name: "Admin", role, is_active: true },
    organizationId: "org",
    isAuthenticated: true,
    isInitializing: false,
    login: vi.fn(),
    logout: vi.fn(),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ResetTestData", () => {
  it("is hidden for non-admin users", () => {
    render(<AuthContext.Provider value={auth("developer")}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    expect(screen.queryByRole("heading", { name: /Reset Test Application Data/ })).toBeNull();
  });

  it("is visible for organization_admin", () => {
    render(<AuthContext.Provider value={auth("organization_admin")}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    expect(screen.getByText("Reset Test Application Data")).toBeInTheDocument();
  });

  it("is visible for super_admin", () => {
    render(<AuthContext.Provider value={auth("super_admin")}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    expect(screen.getByText("Reset Test Application Data")).toBeInTheDocument();
  });

  it("physical database warning is always visible for admins after preview", async () => {
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(screen.getByText(/This operation will not delete any physical databases/)).toBeInTheDocument());
  });

  it("execute button not present before preview and preview calls endpoint", async () => {
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    expect(screen.queryByText("Delete All Test Connections and Workspaces")).toBeNull();
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(api.previewCleanup).toHaveBeenCalled());
  });

  it("preview displays all returned counts and does not call execute", async () => {
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(screen.getByText("Connections: 1")).toBeInTheDocument());
    expect(api.executeCleanup).not.toHaveBeenCalled();
  });

  it("execute remains disabled for incorrect confirmation and enabled for exact text", async () => {
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(screen.getByLabelText("confirmation-input")).toBeInTheDocument());
    const input = screen.getByLabelText("confirmation-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "DELETE" } });
    const btn = screen.getByText("Delete All Test Connections and Workspaces") as HTMLButtonElement;
    expect(btn).toBeDisabled();
    fireEvent.change(input, { target: { value: "DELETE TEST APP DATA" } });
    expect(btn).not.toBeDisabled();
  });

  it("shows confirmation dialog before execute and cancelling does not call execute", async () => {
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(screen.getByLabelText("confirmation-input")).toBeInTheDocument());
    const input = screen.getByLabelText("confirmation-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "DELETE TEST APP DATA" } });
    const btn = screen.getByText("Delete All Test Connections and Workspaces");
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByText(/Physical databases and Azure resources will not be deleted/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Cancel"));
    expect(api.executeCleanup).not.toHaveBeenCalled();
  });

  it("execute sends correct payload and on success shows correlation id, summary, refreshes and clears confirmation", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={refresh} /></AuthContext.Provider>);
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(screen.getByLabelText("confirmation-input")).toBeInTheDocument());
    const input = screen.getByLabelText("confirmation-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "DELETE TEST APP DATA" } });
    fireEvent.click(screen.getByText("Delete All Test Connections and Workspaces"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() => expect(api.executeCleanup).toHaveBeenCalled());
    // verify payload
    const call = (api.executeCleanup as any).mock.calls[0];
    expect(call[0]).toBe("org");
    expect(call[1]).toEqual({ confirmation: "DELETE TEST APP DATA", keep_default_workspace: true });
    await waitFor(() => expect(screen.getByText("Cleanup Result")).toBeInTheDocument());
    expect(screen.getByText(/Correlation ID/)).toBeInTheDocument();
    expect(refresh).toHaveBeenCalled();
    // confirmation cleared and execute disabled
    expect(screen.getByLabelText("confirmation-input")).toHaveValue("");
    expect(screen.getByText("Delete All Test Connections and Workspaces")).toBeDisabled();
  });

  it("handles 403 administrator required and guard disabled messages", async () => {
    (api.executeCleanup as any).mockRejectedValueOnce(new ApiClientError("forbidden", 403, "forbidden"));
    (api.previewCleanup as any).mockResolvedValueOnce({ counts: {}, one_default_workspace_required: false });
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(api.previewCleanup).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("confirmation-input"), { target: { value: "DELETE TEST APP DATA" } });
    fireEvent.click(screen.getByText("Delete All Test Connections and Workspaces"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Administrator permission required/));

    // guard disabled message
    (api.executeCleanup as any).mockRejectedValueOnce(new ApiClientError("disabled", 403, "Test data cleanup is disabled by environment"));
    fireEvent.click(screen.getByText("Delete All Test Connections and Workspaces"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/ALLOW_TEST_DATA_CLEANUP must be enabled/));
  });

  it("shows transaction correlation id on 500 and network failure allows retry", async () => {
    (api.executeCleanup as any).mockRejectedValueOnce(new ApiClientError("server", 500, { correlation_id: "x-1" }));
    (api.previewCleanup as any).mockResolvedValueOnce({ counts: {}, one_default_workspace_required: false });
    const refresh = vi.fn().mockResolvedValue(undefined);
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={refresh} /></AuthContext.Provider>);
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(api.previewCleanup).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("confirmation-input"), { target: { value: "DELETE TEST APP DATA" } });
    fireEvent.click(screen.getByText("Delete All Test Connections and Workspaces"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/correlation id: x-1/));

    // network failure for preview then retry
    (api.previewCleanup as any).mockRejectedValueOnce(new ApiClientError("network", 0, undefined));
    (api.previewCleanup as any).mockResolvedValueOnce({ counts: { connections: 2 }, one_default_workspace_required: false });
    // first click triggers network failure, second click retries and returns counts:2
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/network/));
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(screen.getByText(/Connections: 2/)).toBeInTheDocument());
  });

  it("never renders secret references or credentials", async () => {
    render(<AuthContext.Provider value={auth()}><ResetTestData organizationId="org" onRefresh={vi.fn()} /></AuthContext.Provider>);
    fireEvent.click(screen.getByText("Preview Cleanup"));
    await waitFor(() => expect(screen.getByText(/Connections:/)).toBeInTheDocument());
    expect(screen.queryByText(/secret/)).toBeNull();
    expect(screen.queryByText(/connection_string/)).toBeNull();
  });
});
