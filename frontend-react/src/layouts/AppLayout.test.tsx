import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import type { Session } from "../models/auth";
import { SESSION_STORAGE_KEY } from "../api/client";
import { AuthProvider } from "../stores/auth-store";
import { AppLayout } from "./AppLayout";

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

function renderLayout(path = "/app/dashboard") {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/app" element={<AppLayout />}>
            <Route path="dashboard" element={<p>Dashboard content</p>} />
            <Route path="investigations/:investigationId" element={<p>Investigation content</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AppLayout", () => {
  beforeEach(() => localStorage.clear());

  it("renders exactly the currently supported navigation areas", () => {
    renderLayout();

    const navigation = screen.getByRole("navigation", { name: "Application navigation" });
    expect(navigation.querySelectorAll("a")).toHaveLength(6);
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/app/dashboard");
    expect(screen.getByRole("link", { name: "Learning Loop" })).toHaveAttribute("href", "/app/learning");
  });

  it("renders the active page title, user email, and role", () => {
    renderLayout("/app/investigations/INV-1");

    expect(screen.getByRole("heading", { name: "Investigation" })).toBeInTheDocument();
    expect(screen.getByText("admin@example.com - organization_admin")).toBeInTheDocument();
    expect(screen.getByText("Investigation content")).toBeInTheDocument();
  });

  it("keeps logout available from the authenticated header", () => {
    renderLayout();

    fireEvent.click(screen.getByRole("button", { name: "Logout" }));

    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(screen.queryByText("admin@example.com - organization_admin")).not.toBeInTheDocument();
  });
});
