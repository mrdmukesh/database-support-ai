import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Session } from "../models/auth";
import { login as loginRequest } from "../api/auth-api";
import {
  SESSION_EXPIRED_EVENT,
  SESSION_STORAGE_KEY,
} from "../api/client";
import { useAuth } from "../hooks/use-auth";
import { AuthProvider } from "./auth-store";

vi.mock("../api/auth-api", () => ({ login: vi.fn() }));

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

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe("AuthProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(loginRequest).mockReset();
  });

  it("restores the current user and organization from stored session", () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));

    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(session.user);
    expect(result.current.organizationId).toBe("ORG-1");
  });

  it("stores a successful login and updates authentication state", async () => {
    vi.mocked(loginRequest).mockResolvedValue(session);
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login({ email: "admin@example.com", password: "password" });
    });

    expect(result.current.session).toEqual(session);
    expect(result.current.isAuthenticated).toBe(true);
    expect(JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) ?? "null")).toEqual(session);
  });

  it("logs out and removes the stored session", () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => result.current.logout());

    expect(result.current.session).toBeNull();
    expect(result.current.user).toBeNull();
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it("clears React authentication state when the shared client reports expiration", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT)));

    await waitFor(() => expect(result.current.isAuthenticated).toBe(false));
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });
});
