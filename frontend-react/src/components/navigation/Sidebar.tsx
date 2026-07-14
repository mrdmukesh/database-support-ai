import { NavLink } from "react-router-dom";
import { useAuth } from "../../hooks/use-auth";

const navigation = [
  ["Dashboard", "/app/dashboard"],
  ["Workspaces", "/app/workspaces"],
  ["Connections", "/app/connections"],
  ["Documents", "/app/documents"],
  ["Investigations", "/app/investigations"],
  ["Learning Loop", "/app/learning"],
] as const;

export function Sidebar() {
  const { user } = useAuth();
  const canManageUsers = user?.role === "super_admin" || user?.role === "organization_admin";
  return (
    <aside className="application-sidebar">
      <div className="application-brand" aria-label="LegacyDB Support Copilot">
        <span className="application-brand-mark" aria-hidden="true">L</span>
        <span>LegacyDB Copilot</span>
      </div>
      <nav aria-label="Application navigation">
        {navigation.map(([label, path]) => (
          <NavLink key={path} to={path}>
            {label}
          </NavLink>
        ))}
      </nav>
      {canManageUsers && <nav aria-label="Administration navigation"><span className="navigation-label">Administration</span><NavLink to="/app/admin/users">Users &amp; Access</NavLink><NavLink to="/app/evaluation">Evaluation</NavLink></nav>}
    </aside>
  );
}
