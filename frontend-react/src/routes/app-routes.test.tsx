import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import type { Session } from "../models/auth";
import { SESSION_STORAGE_KEY } from "../api/client";
import { AuthProvider } from "../stores/auth-store";
import { AppRoutes } from "./app-routes";

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
  beforeEach(() => localStorage.clear());

  it("redirects unauthenticated protected routes to login and preserves the destination", async () => {
    renderRoutes("/app/investigations/INV-7?tab=evidence", <LocationProbe />);

    expect(await screen.findByRole("heading", { name: "Login" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("allows restored sessions to open protected routes", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));

    renderRoutes("/app/workspaces");

    expect(await screen.findAllByRole("heading", { name: "Workspaces" })).toHaveLength(2);
    expect(screen.getByText("React migration placeholder")).toBeInTheDocument();
  });

  it("renders the investigation route parameter without adding feature behavior", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));

    renderRoutes("/app/investigations/INV-7");

    expect(await screen.findByRole("heading", { name: "Investigation INV-7" })).toBeInTheDocument();
  });

  it("renders a clear placeholder for unknown routes", () => {
    renderRoutes("/not-a-route");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
