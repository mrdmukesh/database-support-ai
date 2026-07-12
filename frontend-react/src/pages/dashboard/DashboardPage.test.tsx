import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getApiHealth, getDashboardSummary, getDisclaimer } from "../../api/dashboard-api";
import { listWorkspaces } from "../../api/workspace-api";
import { useAuth } from "../../hooks/use-auth";
import { DashboardPage } from "./DashboardPage";

vi.mock("../../api/dashboard-api", () => ({ getApiHealth: vi.fn(), getDashboardSummary: vi.fn(), getDisclaimer: vi.fn() }));
vi.mock("../../api/workspace-api", () => ({ listWorkspaces: vi.fn() }));
vi.mock("../../hooks/use-auth", () => ({ useAuth: vi.fn() }));

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({ session: null, user: null, organizationId: "ORG-1", isAuthenticated: true, login: vi.fn(), logout: vi.fn() });
    vi.mocked(getDashboardSummary).mockResolvedValue({ organizations: 1, users: 2, active_subscriptions: 9, documents: 3, incidents: 4 });
    vi.mocked(getApiHealth).mockResolvedValue({ status: "healthy", components: [] });
    vi.mocked(getDisclaimer).mockResolvedValue(["Verify AI output"]);
    vi.mocked(listWorkspaces).mockResolvedValue([{ id: "W1", organization_id: "ORG-1", name: "Finance", slug: "finance", is_active: true }]);
  });

  it("displays only current counts, workspace information, disclaimer, and API status", async () => {
    render(<DashboardPage />);
    expect(screen.getByText("Loading dashboard...")).toBeInTheDocument();
    expect(await screen.findByText("API healthy")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
    expect(screen.getByText("Verify AI output")).toBeInTheDocument();
    expect(screen.getByText("Organizations").nextElementSibling).toHaveTextContent("1");
    expect(screen.queryByText("Active subscriptions")).not.toBeInTheDocument();
  });

  it("preserves empty workspace and disclaimer states", async () => {
    vi.mocked(listWorkspaces).mockResolvedValue([]);
    vi.mocked(getDisclaimer).mockResolvedValue([]);
    render(<DashboardPage />);
    expect(await screen.findByText("No workspaces yet.")).toBeInTheDocument();
    expect(screen.getByText("No disclaimer is available.")).toBeInTheDocument();
  });

  it("preserves dashboard error state", async () => {
    vi.mocked(getDashboardSummary).mockRejectedValue(new Error("Forbidden"));
    render(<DashboardPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Forbidden");
  });
});
