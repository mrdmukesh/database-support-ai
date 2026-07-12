import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthState } from "../../stores/auth-store";
import { useAuth } from "../../hooks/use-auth";
import { LoginPage } from "./LoginPage";

vi.mock("../../hooks/use-auth", () => ({ useAuth: vi.fn() }));

const login = vi.fn<AuthState["login"]>();

function Destination() {
  const location = useLocation();
  return <h1>Destination {location.pathname}</h1>;
}

function renderLogin(initialEntry: string | { pathname: string; state: unknown } = "/login") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app/*" element={<Destination />} />
      </Routes>
    </MemoryRouter>,
  );
}

function submitCredentials() {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: " admin@example.com " } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass123!" } });
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    login.mockReset();
    vi.mocked(useAuth).mockReturnValue({
      session: null,
      user: null,
      organizationId: null,
      isAuthenticated: false,
      login,
      logout: vi.fn(),
    });
  });

  it("submits the current email and password payload and creates login state", async () => {
    login.mockResolvedValue({
      access_token: "token",
      token_type: "bearer",
      user: {
        id: "USER-1",
        organization_id: "ORG-1",
        email: "admin@example.com",
        full_name: "Admin",
        role: "organization_admin",
        is_active: true,
      },
    });
    renderLogin();

    submitCredentials();

    await waitFor(() => expect(login).toHaveBeenCalledWith({
      email: "admin@example.com",
      password: "StrongPass123!",
    }));
  });

  it("shows invalid-credential errors from the current API", async () => {
    login.mockRejectedValue(new Error("Invalid credentials"));
    renderLogin();

    submitCredentials();

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
  });

  it("shows normalized server errors", async () => {
    login.mockRejectedValue(new Error("Authentication service unavailable"));
    renderLogin();

    submitCredentials();

    expect(await screen.findByRole("alert")).toHaveTextContent("Authentication service unavailable");
  });

  it("disables the form and displays loading state while login is pending", async () => {
    login.mockReturnValue(new Promise(() => undefined));
    renderLogin();

    submitCredentials();

    expect(await screen.findByRole("button", { name: "Logging in..." })).toBeDisabled();
    expect(screen.getByLabelText("Email")).toBeDisabled();
    expect(screen.getByLabelText("Password")).toBeDisabled();
  });

  it("redirects to the preserved destination after successful login", async () => {
    login.mockResolvedValue({
      access_token: "token",
      token_type: "bearer",
      user: {
        id: "USER-1",
        organization_id: "ORG-1",
        email: "admin@example.com",
        full_name: "Admin",
        role: "organization_admin",
        is_active: true,
      },
    });
    renderLogin({ pathname: "/login", state: { from: "/app/documents" } });

    submitCredentials();

    expect(await screen.findByRole("heading", { name: "Destination /app/documents" })).toBeInTheDocument();
  });
});
