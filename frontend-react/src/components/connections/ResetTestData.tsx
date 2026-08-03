import { useState } from "react";
import { useAuth } from "../../hooks/use-auth";
import { previewCleanup, executeCleanup } from "../../api/admin-api";
import type { CleanupPreviewResponse, CleanupExecuteRequest, CleanupExecuteResponse } from "../../models/admin";
import { ConfirmationDialog } from "../common/ConfirmationDialog";
import { ApiClientError } from "../../api/client";

export function ResetTestData({ organizationId, onRefresh }: { organizationId: string | null; onRefresh: () => Promise<void> }) {
  const auth = useAuth();
  const userRole = auth.user?.role ?? "";
  const isAdmin = userRole === "organization_admin" || userRole === "super_admin";
  const [preview, setPreview] = useState<CleanupPreviewResponse | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [executeResult, setExecuteResult] = useState<CleanupExecuteResponse | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [running, setRunning] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isAdmin || !organizationId) return null;

  async function handlePreview() {
    setError(null);
    setLoadingPreview(true);
    try {
      const resp = await previewCleanup(organizationId!);
      setPreview(resp);
    } catch (e: unknown) {
      if (e instanceof ApiClientError) {
        if (e.status === 403) {
          const det = String(e.detail ?? "").toLowerCase();
          if (det.includes("allow_test_data_cleanup") || det.includes("cleanup is disabled") || det.includes("disabled")) {
            setError("Cleanup guard disabled: ALLOW_TEST_DATA_CLEANUP must be enabled");
          } else {
            setError("Administrator permission required");
          }
        } else setError(e.message);
      } else {
        setError((e as Error).message || String(e));
      }
    } finally {
      setLoadingPreview(false);
    }
  }

  async function doExecute() {
    setError(null);
    setRunning(true);
    try {
      const body: CleanupExecuteRequest = { confirmation: "DELETE TEST APP DATA", keep_default_workspace: true };
      const resp = await executeCleanup(organizationId!, body);
      setExecuteResult(resp);
      // refresh connections and workspaces
      await onRefresh();
      setConfirmation("");
    } catch (e: unknown) {
      if (e instanceof ApiClientError) {
        if (e.status === 403) {
          const det = String(e.detail ?? "").toLowerCase();
          if (det.includes("allow_test_data_cleanup") || det.includes("cleanup is disabled") || det.includes("disabled")) {
            setError("Cleanup guard disabled: ALLOW_TEST_DATA_CLEANUP must be enabled");
          } else {
            setError("Administrator permission required");
          }
        } else if (e.status === 400) setError((e.detail as any) || e.message);
        else if (e.status === 500) {
          // if the server included a correlation_id in detail, surface it
          const det = e.detail as any;
          if (det && typeof det === "object" && det.correlation_id) {
            setError(`Transaction failed (correlation id: ${det.correlation_id})`);
          } else setError(e.message);
        } else setError(e.message);
      } else {
        setError((e as Error).message || String(e));
      }
    } finally {
      setRunning(false);
      setConfirmOpen(false);
    }
  }

  function handleExecute() {
    // open confirmation dialog — final confirmation required
    setConfirmOpen(true);
  }

  const previewCounts = preview?.counts ?? {};

  return (
    <section className="reset-test-data">
      <h3>Reset Test Application Data</h3>
      <p className="warning">This removes saved connections, investigations, related evidence, and user-created workspaces from the test application. It does not delete any physical database or Azure resource.</p>
      <div className="controls">
        <button type="button" onClick={handlePreview} disabled={loadingPreview}>{loadingPreview ? "Previewing..." : "Preview Cleanup"}</button>
      </div>
      {error ? <div role="alert" className="form-message error">{error}</div> : null}

      {preview ? (
        <div className="preview-result">
          <h4>Preview</h4>
          <ul>
            <li>Connections: {previewCounts.connections ?? 0}</li>
            <li>Workspaces: {previewCounts.workspaces ?? 0}</li>
            <li>Investigations: {previewCounts.investigations ?? 0}</li>
            <li>Evidence: {previewCounts.evidence ?? 0}</li>
            <li>Execution traces: {previewCounts.execution_traces ?? 0}</li>
            <li>Planner selections: {previewCounts.planner_selections ?? 0}</li>
            <li>Agentic steps: {previewCounts.agentic_steps ?? 0}</li>
            <li>LLM audit rows: {previewCounts.llm_invocation_audit ?? 0}</li>
            <li>Feedback: {previewCounts.feedback ?? 0}</li>
            <li>Reports: {previewCounts.verification_checks ?? 0}</li>
          </ul>
          <p>Default workspace behavior: {preview.one_default_workspace_required ? "A default workspace will be created" : "No default workspace required"}</p>
          <p className="warning small">This operation will not delete any physical databases or Azure resources.</p>

          <div className="execute-controls">
            <label htmlFor="reset-confirm">Type <strong>DELETE TEST APP DATA</strong> to enable:</label>
            <input id="reset-confirm" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} aria-label="confirmation-input" />
            <button type="button" onClick={handleExecute} disabled={preview == null || confirmation !== "DELETE TEST APP DATA" || running}>{running ? "Deleting..." : "Delete All Test Connections and Workspaces"}</button>
          </div>
          <ConfirmationDialog open={confirmOpen} title="Confirm destructive cleanup" message={`Connections: ${previewCounts.connections ?? 0}\nWorkspaces: ${previewCounts.workspaces ?? 0}\nInvestigations: ${previewCounts.investigations ?? 0}\n\nPhysical databases and Azure resources will not be deleted.`} confirmLabel="Delete" cancelLabel="Cancel" onConfirm={doExecute} onCancel={() => setConfirmOpen(false)} />
        </div>
      ) : null}

      {executeResult ? (
        <div className="execute-result">
          <h4>Cleanup Result</h4>
          <p>Correlation ID: {executeResult.correlation_id ?? "(none)"}</p>
          <pre>{JSON.stringify(executeResult.summary ?? executeResult, null, 2)}</pre>
        </div>
      ) : null}
    </section>
  );
}

export default ResetTestData;
