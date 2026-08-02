import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthContext, type AuthState } from "../../stores/auth-store";
import type { User } from "../../models/auth";
import { ModelManagementPage } from "./ModelManagementPage";

vi.mock("../../api/model-management-api", () => ({
  loadCatalog: vi.fn().mockResolvedValue([
    { id: "fast", display_name: "Fast", description: "Routine work", model_category: "fast", availability_status: "available", premium: false, automatic_eligible: true, enabled: true },
  ]),
  loadModelPolicy: vi.fn().mockResolvedValue({ user_selection_enabled: false, automatic_mode_enabled: false, fallback_enabled: false, require_premium_approval: true }),
  loadSelectionAudit: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createCatalogModel: vi.fn(),
  updateCatalogModel: vi.fn(),
  updateModelPolicy: vi.fn(),
}));

function auth(role: User["role"]): AuthState {
  return {
    session: null,
    user: { id: "user", organization_id: "org", email: "user@example.com", full_name: "User", role, is_active: true },
    organizationId: "org", isAuthenticated: true, isInitializing: false,
    login: vi.fn(), logout: vi.fn(),
  };
}

describe("ModelManagementPage", () => {
  it("blocks ordinary users", () => {
    render(<AuthContext.Provider value={auth("developer")}><ModelManagementPage /></AuthContext.Provider>);
    expect(screen.getByRole("alert")).toHaveTextContent("not authorized");
  });

  it("shows the governed catalog to administrators", async () => {
    render(<AuthContext.Provider value={auth("organization_admin")}><ModelManagementPage /></AuthContext.Provider>);
    expect(screen.getByRole("heading", { name: "Model Management" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Fast")).toBeInTheDocument());
    expect(screen.getByRole("form", { name: "Add model configuration" })).toBeInTheDocument();
  });
});
