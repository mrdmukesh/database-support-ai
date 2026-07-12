import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createDefaultWorkspace,
  createOrganization,
  listOrganizations,
  signup,
} from "../../api/auth-api";
import { useAuth } from "../../hooks/use-auth";
import type { AuthState } from "../../stores/auth-store";
import { SignupPage } from "./SignupPage";

vi.mock("../../api/auth-api", () => ({
  createDefaultWorkspace: vi.fn(),
  createOrganization: vi.fn(),
  listOrganizations: vi.fn(),
  signup: vi.fn(),
}));
vi.mock("../../hooks/use-auth", () => ({ useAuth: vi.fn() }));

const login = vi.fn<AuthState["login"]>();
const organization = { id: "ORG-1", name: "Acme", slug: "acme", is_active: true };

function renderSignup() {
  return render(
    <MemoryRouter initialEntries={["/signup"]}>
      <Routes>
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/app/dashboard" element={<h1>Dashboard destination</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

function completeForm() {
  fireEvent.change(screen.getByLabelText("Organization name"), { target: { value: "Acme" } });
  fireEvent.change(screen.getByLabelText("Organization slug"), { target: { value: "acme" } });
  fireEvent.change(screen.getByLabelText("Admin name"), { target: { value: "Admin User" } });
  fireEvent.change(screen.getByLabelText("Admin email"), { target: { value: "admin@example.com" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass123!" } });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));
}

describe("SignupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(createOrganization).mockResolvedValue(organization);
    vi.mocked(signup).mockResolvedValue({
      id: "USER-1",
      organization_id: "ORG-1",
      email: "admin@example.com",
      full_name: "Admin User",
      role: "organization_admin",
      is_active: true,
    });
    vi.mocked(createDefaultWorkspace).mockResolvedValue({
      id: "WS-1",
      organization_id: "ORG-1",
      name: "Default Workspace",
      slug: "default-workspace",
      is_active: true,
    });
    login.mockResolvedValue({
      access_token: "token",
      token_type: "bearer",
      user: {
        id: "USER-1",
        organization_id: "ORG-1",
        email: "admin@example.com",
        full_name: "Admin User",
        role: "organization_admin",
        is_active: true,
      },
    });
    vi.mocked(useAuth).mockReturnValue({
      session: null,
      user: null,
      organizationId: null,
      isAuthenticated: false,
      isInitializing: false,
      login,
      logout: vi.fn(),
    });
  });

  it("preserves organization, signup, consent, and login payloads", async () => {
    renderSignup();
    completeForm();
    fireEvent.click(screen.getByLabelText("Product updates"));
    submit();

    await waitFor(() => expect(signup).toHaveBeenCalled());
    expect(createOrganization).toHaveBeenCalledWith({ name: "Acme", slug: "acme" });
    expect(signup).toHaveBeenCalledWith({
      organization_id: "ORG-1",
      email: "admin@example.com",
      password: "StrongPass123!",
      full_name: "Admin User",
      role: "organization_admin",
      consents: [
        "terms_of_service",
        "privacy_policy",
        "document_processing",
        "ai_verification_required",
        "product_updates",
      ],
      ip_address: "127.0.0.1",
    });
    expect(login).toHaveBeenCalledWith({ email: "admin@example.com", password: "StrongPass123!" });
    expect(createDefaultWorkspace).toHaveBeenCalledWith("ORG-1");
  });

  it("uses the existing organization when creation reports a duplicate", async () => {
    vi.mocked(createOrganization).mockRejectedValue(new Error("Organization already exists"));
    vi.mocked(listOrganizations).mockResolvedValue([organization]);
    renderSignup();
    completeForm();
    submit();

    await waitFor(() => expect(signup).toHaveBeenCalled());
    expect(listOrganizations).toHaveBeenCalled();
    expect(signup).toHaveBeenCalledWith(expect.objectContaining({ organization_id: "ORG-1" }));
  });

  it("preserves required consent controls and current role choices", () => {
    renderSignup();

    expect(screen.getByLabelText("I agree to the Terms of Service")).toBeRequired();
    expect(screen.getByLabelText("I agree to the Privacy Policy")).toBeRequired();
    expect(screen.getByLabelText("I consent to processing uploaded documents")).toBeRequired();
    expect(screen.getByLabelText("I understand AI-generated answers require verification")).toBeRequired();
    expect(screen.getByRole("option", { name: "Organization Admin" })).toHaveValue("organization_admin");
    expect(screen.getByRole("option", { name: "DBA" })).toHaveValue("dba");
    expect(screen.getByRole("option", { name: "Developer" })).toHaveValue("developer");
  });

  it("shows API errors without continuing signup", async () => {
    vi.mocked(createOrganization).mockRejectedValue(new Error("Organization service unavailable"));
    renderSignup();
    completeForm();
    submit();

    expect(await screen.findByRole("alert")).toHaveTextContent("Organization service unavailable");
    expect(signup).not.toHaveBeenCalled();
    expect(login).not.toHaveBeenCalled();
  });

  it("redirects to dashboard after the current signup sequence", async () => {
    renderSignup();
    completeForm();
    submit();

    expect(await screen.findByRole("heading", { name: "Dashboard destination" })).toBeInTheDocument();
  });
});
