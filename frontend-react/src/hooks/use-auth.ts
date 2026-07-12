import { useContext } from "react";
import { AuthContext, type AuthState } from "../stores/auth-store";

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be used within AuthProvider.");
  return auth;
}
