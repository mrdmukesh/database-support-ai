import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { login as loginRequest } from "../api/auth-api";
import {
  SESSION_EXPIRED_EVENT,
  SESSION_STORAGE_KEY,
} from "../api/client";
import type { LoginRequest, Session, User } from "../models/auth";

export interface AuthState {
  session: Session | null;
  user: User | null;
  organizationId: string | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (credentials: LoginRequest, signal?: AbortSignal) => Promise<Session>;
  logout: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);

function restoreSession(): Session | null {
  try {
    const value = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!value) return null;
    const session = JSON.parse(value) as Partial<Session>;
    if (!session.access_token || !session.user?.id || !session.user.organization_id) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      return null;
    }
    return session as Session;
  } catch {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    setSession(restoreSession());
    setIsInitializing(false);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setSession(null);
  }, []);

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, logout);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, logout);
  }, [logout]);

  const login = useCallback(async (credentials: LoginRequest, signal?: AbortSignal) => {
    const nextSession = await loginRequest(credentials, signal);
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(nextSession));
    setSession(nextSession);
    return nextSession;
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      session,
      user: session?.user ?? null,
      organizationId: session?.user.organization_id ?? null,
      isAuthenticated: Boolean(session?.access_token && session.user),
      isInitializing,
      login,
      logout,
    }),
    [login, logout, session, isInitializing],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
