import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listConnections } from "../../api/connection-api";
import { listWorkspaces } from "../../api/workspace-api";
import { InvestigationForm } from "../../components/investigation/InvestigationForm";
import { InvestigationProvider } from "../../features/investigation/investigation-context";
import { useInvestigation } from "../../features/investigation/use-investigation";
import { useAuth } from "../../hooks/use-auth";
import type { DatabaseConnection } from "../../models/connection";
import type { Workspace } from "../../models/workspace";
import { formatSafeText } from "../../utils/investigation-formatters";

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Investigation setup failed.";
}

function InvestigationPageContent() {
  const { organizationId } = useAuth();
  const investigation = useInvestigation();
  const navigate = useNavigate();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [isLoadingOptions, setIsLoadingOptions] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationId) {
      setLoadError("An authenticated organization is required.");
      setIsLoadingOptions(false);
      return;
    }

    const controller = new AbortController();
    setIsLoadingOptions(true);
    setLoadError(null);
    Promise.all([
      listWorkspaces(organizationId, controller.signal),
      listConnections(organizationId, undefined, controller.signal),
    ])
      .then(([workspaceRows, connectionRows]) => {
        setWorkspaces(workspaceRows);
        setConnections(connectionRows);
      })
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setLoadError(messageOf(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingOptions(false);
      });
    return () => controller.abort();
  }, [organizationId]);

  useEffect(() => {
    const id = investigation.currentInvestigationId?.trim();
    if (id) navigate(`/app/investigations/${encodeURIComponent(id)}`);
  }, [investigation.currentInvestigationId, navigate]);

  const inlineFallback = investigation.currentResponse?.investigation_id?.trim()
    ? ""
    : formatSafeText(investigation.currentResponse?.assistant_message.content);

  return (
    <section className="management-page" aria-labelledby="investigation-page-title">
      <div className="management-page-heading">
        <p className="eyebrow">Database support</p>
        <h2 id="investigation-page-title">Investigations</h2>
      </div>
      {loadError ? <div className="form-message error" role="alert">{loadError}</div> : null}
      {isLoadingOptions ? (
        <p role="status">Loading investigation options...</p>
      ) : !loadError ? (
        <InvestigationForm workspaces={workspaces} connections={connections} />
      ) : null}
      {inlineFallback ? (
        <section aria-labelledby="inline-investigation-result-title">
          <h3 id="inline-investigation-result-title">Investigation result</h3>
          <pre>{inlineFallback}</pre>
        </section>
      ) : null}
    </section>
  );
}

export function InvestigationPage() {
  return (
    <InvestigationProvider>
      <InvestigationPageContent />
    </InvestigationProvider>
  );
}
