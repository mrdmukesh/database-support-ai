import { useEffect, useState } from "react";
import {
  getApiHealth,
  getDashboardSummary,
  getDisclaimer,
  type ApiHealth,
  type DashboardSummary,
} from "../../api/dashboard-api";
import { listWorkspaces } from "../../api/workspace-api";
import { useAuth } from "../../hooks/use-auth";
import type { Workspace } from "../../models/workspace";

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Dashboard request failed.";
}

export function DashboardPage() {
  const { organizationId } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [disclaimers, setDisclaimers] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationId) return;
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    void Promise.all([
      getDashboardSummary(controller.signal),
      listWorkspaces(organizationId, controller.signal),
      getDisclaimer(controller.signal),
      getApiHealth(controller.signal),
    ])
      .then(([summaryResult, workspaceRows, disclaimerRows, healthResult]) => {
        setSummary(summaryResult);
        setWorkspaces(workspaceRows);
        setDisclaimers(disclaimerRows);
        setHealth(healthResult);
      })
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setError(messageOf(cause));
      })
      .finally(() => setIsLoading(false));
    return () => controller.abort();
  }, [organizationId]);

  if (isLoading) return <p>Loading dashboard...</p>;
  if (error) return <div className="form-message error" role="alert">{error}</div>;
  if (!summary) return <p className="empty-state">Dashboard summary is unavailable.</p>;

  const counts = [
    ["Organizations", summary.organizations],
    ["Users", summary.users],
    ["Documents", summary.documents],
    ["Incidents", summary.incidents],
  ] as const;

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-page-title">
      <div className="management-page-heading">
        <p className="eyebrow">Overview</p>
        <h2 id="dashboard-page-title">Dashboard</h2>
        <p className="api-health-status">API {health?.status ?? "unavailable"}</p>
      </div>
      <div className="dashboard-counts">
        {counts.map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}
      </div>
      <div className="dashboard-details">
        <section className="dashboard-panel" aria-labelledby="dashboard-workspaces-title">
          <h3 id="dashboard-workspaces-title">Workspaces</h3>
          {workspaces.length ? (
            <table>
              <thead><tr><th>Name</th><th>Slug</th><th>Status</th></tr></thead>
              <tbody>{workspaces.map((workspace) => (
                <tr key={workspace.id}><td>{workspace.name}</td><td>{workspace.slug}</td><td>{workspace.is_active ? "Active" : "Inactive"}</td></tr>
              ))}</tbody>
            </table>
          ) : <p className="empty-state">No workspaces yet.</p>}
        </section>
        <section className="dashboard-panel" aria-labelledby="dashboard-disclaimer-title">
          <h3 id="dashboard-disclaimer-title">AI disclaimer</h3>
          {disclaimers.length ? <ul>{disclaimers.map((line) => <li key={line}>{line}</li>)}</ul> : <p className="empty-state">No disclaimer is available.</p>}
        </section>
      </div>
    </section>
  );
}
