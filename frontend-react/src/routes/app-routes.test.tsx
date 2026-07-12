import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Session } from "../models/auth";
import { SESSION_STORAGE_KEY } from "../api/client";
import { AuthProvider } from "../stores/auth-store";
import { AppRoutes } from "./app-routes";

const listWorkspaces = vi.fn();

vi.mock("../pages/investigations/InvestigationPage", () => ({
  InvestigationPage: () => <div>Investigation page base route</div>,
}));

vi.mock("../pages/investigations/InvestigationResultPage", () => ({
  InvestigationResultPage: () => {
    const { investigationId } = useParams();
    return <div>Investigation detail: {investigationId}</div>;
  },
}));

vi.mock("../api/workspace-api", () => ({
  listWorkspaces: (...args: unknown[]) => listWorkspaces(...args),
}));

const session: Session = {
  access_token: "token-1",
  token_type: "bearer",
  user: {
    id: "USER-1",
    organization_id: "ORG-1",
    email: "admin@example.com",
    full_name: "Admin",
    role: "organization_admin",
    is_active: true,
  },
};

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

function renderRoutes(path: string, children?: ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
        {children}
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("application routes", () => {
  beforeEach(() => {
    localStorage.clear();
    listWorkspaces.mockReset().mockResolvedValue([]);
  });

  it("redirects unauthenticated protected routes to login and preserves the destination", async () => {
    renderRoutes("/app/investigations/INV-7?tab=evidence", <LocationProbe />);

    expect(await screen.findByRole("heading", { name: "Login" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("allows restored sessions to open protected routes", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));

    renderRoutes("/app/workspaces");

    const headings = await screen.findAllByRole("heading", { name: "Workspaces" });
    expect(headings).toHaveLength(2);
    expect(screen.getByRole("status")).toHaveTextContent("No workspaces yet.");
  });

  it("renders a valid investigation route ID to the result page", () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));

    renderRoutes("/app/investigations/INV-7");

    expect(screen.getByText("Investigation detail: INV-7")).toBeInTheDocument();
  });

  it("decodes encoded investigation route IDs", () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));

    renderRoutes("/app/investigations/INV%207");

    expect(screen.getByText("Investigation detail: INV 7")).toBeInTheDocument();
  });

  it("renders the base investigation route without an ID", () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));

    renderRoutes("/app/investigations");

    expect(screen.getByText("Investigation page base route")).toBeInTheDocument();
  });

  it("renders a clear placeholder for unknown routes", () => {
    renderRoutes("/not-a-route");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
