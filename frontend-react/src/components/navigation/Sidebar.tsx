import { NavLink } from "react-router-dom";

const navigation = [
  ["Dashboard", "/app/dashboard"],
  ["Workspaces", "/app/workspaces"],
  ["Connections", "/app/connections"],
  ["Documents", "/app/documents"],
  ["Investigations", "/app/investigations"],
  ["Learning Loop", "/app/learning"],
] as const;

export function Sidebar() {
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
    </aside>
  );
}
