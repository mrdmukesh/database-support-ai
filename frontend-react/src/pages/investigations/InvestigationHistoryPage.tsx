import { useEffect, useState } from "react";
import { loadInvestigationHistory } from "../../api/investigation-api";
import { listWorkspaces } from "../../api/workspace-api";
import { InvestigationHistoryList } from "../../components/investigation/InvestigationHistoryList";
import { useAuth } from "../../hooks/use-auth";
import type { InvestigationSummary } from "../../models/investigation";
import { LoadingState } from "../../components/common/LoadingState"; import { ErrorMessage } from "../../components/common/ErrorMessage";
export function InvestigationHistoryPage() {
  const { organizationId } = useAuth(); const [rows, setRows] = useState<InvestigationSummary[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  useEffect(() => { const controller = new AbortController(); async function load() { if (!organizationId) { setError("An authenticated organization is required."); setLoading(false); return; } try { const workspaces=await listWorkspaces(organizationId, controller.signal); const groups=await Promise.all(workspaces.map((w) => loadInvestigationHistory(organizationId, w.id, undefined, controller.signal))); setRows(groups.flat().sort((a,b) => b.created_at.localeCompare(a.created_at))); } catch (cause) { if ((cause as {name?:string})?.name !== "AbortError") setError(cause instanceof Error ? cause.message : "History could not be loaded."); } finally { if (!controller.signal.aborted) setLoading(false); } } void load(); return () => controller.abort(); }, [organizationId]);
  return <section className="management-page" aria-labelledby="history-title"><h2 id="history-title">Investigation History</h2>{loading ? <LoadingState message="Loading investigation history..." /> : error ? <ErrorMessage message={error} /> : <InvestigationHistoryList investigations={rows} />}</section>;
}
