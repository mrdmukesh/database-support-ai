import { useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/use-auth";

const routeTitles: Record<string, string> = {
  "/app/dashboard": "Dashboard",
  "/app/workspaces": "Workspaces",
  "/app/connections": "Connections",
  "/app/documents": "Documents",
  "/app/investigations": "Investigations",
  "/app/learning": "Learning Loop",
};

function currentTitle(pathname: string): string {
  if (pathname.startsWith("/app/investigations/")) return "Investigation";
  return routeTitles[pathname] ?? "LegacyDB Support Copilot";
}

export function Header() {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <header className="application-header">
      <h1>{currentTitle(location.pathname)}</h1>
      {user ? (
        <div className="authenticated-user">
          <span className="authenticated-user-label">
            {user.email} - {user.role}
          </span>
          <button type="button" onClick={logout}>Logout</button>
        </div>
      ) : null}
    </header>
  );
}
