import { useCallback, useEffect, useMemo, useState } from "react";
import {
  cancelEvaluationJob,
  createEvaluationJob,
  listEvaluationJobReports,
  listEvaluationJobs,
  regenerateEvaluationReports,
  retryEvaluationJob,
  type EvaluationJob,
  type EvaluationJobReport,
} from "../../api/evaluation-jobs-api";
import { listWorkspaces } from "../../api/workspace-api";
import catalogData from "../../data/evaluation-scenario-catalog.json";
import { useAuth } from "../../hooks/use-auth";
import type { Workspace } from "../../models/workspace";

type CatalogScenario = {
  scenario_id: string;
  domain: string;
  category: string;
  difficulty: string;
  question: string;
  business_description?: string;
  estimated_duration_seconds?: number;
  estimated_token_usage?: number;
};

const catalog = catalogData as CatalogScenario[];
const ACTIVE_STATUSES = ["queued", "preflight", "running", "cancelling"];

const isActive = (status: string) => ACTIVE_STATUSES.includes(status);
const titleCase = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());

export function EvaluationJobControl() {
  const { organizationId, user } = useAuth();
  const [spaces, setSpaces] = useState<Workspace[]>([]);
  const [jobs, setJobs] = useState<EvaluationJob[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [runName, setRunName] = useState(`benchmark-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}`);
  const [confirmed, setConfirmed] = useState(false);

  const [suite, setSuite] = useState("pilot-smoke");
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("all");
  const [category, setCategory] = useState("all");
  const [difficulty, setDifficulty] = useState("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<CatalogScenario | null>(null);

  const [reportsByJob, setReportsByJob] = useState<Record<string, EvaluationJobReport[]>>({});
  const [loadingReports, setLoadingReports] = useState("");

  const canManage = ["super_admin", "organization_admin"].includes(user?.role ?? "");

  const load = useCallback(async () => {
    if (!organizationId) return;
    try {
      const workspaces = await listWorkspaces(organizationId);
      setSpaces(workspaces);
      const selectedWorkspace = workspaceId || workspaces[0]?.id || "";
      if (!workspaceId) setWorkspaceId(selectedWorkspace);
      setJobs(await listEvaluationJobs(selectedWorkspace || undefined));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load evaluation jobs.");
    }
  }, [organizationId, workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!jobs.some(job => isActive(job.status))) return;
    const timer = setInterval(() => void load(), 3000);
    return () => clearInterval(timer);
  }, [jobs, load]);

  const categories = useMemo(() => [...new Set(catalog.map(item => item.category))].sort(), []);
  const domains = useMemo(() => [...new Set(catalog.map(item => item.domain))].sort(), []);

  const filtered = useMemo(() => {
    return catalog.filter(item => {
      return (domain === "all" || item.domain === domain)
        && (category === "all" || item.category === category)
        && (difficulty === "all" || item.difficulty === difficulty)
        && (!query || `${item.scenario_id} ${item.question}`.toLowerCase().includes(query.toLowerCase()));
    });
  }, [query, domain, category, difficulty]);

  const chosen = useMemo(() => catalog.filter(item => selected.includes(item.scenario_id)), [selected]);
  const durationSeconds = chosen.reduce((sum, item) => sum + (item.estimated_duration_seconds || 60), 0);
  const estimatedTokens = chosen.reduce((sum, item) => sum + (item.estimated_token_usage || 2000), 0);
  const estimate = Math.max(0.01, estimatedTokens / 1_000_000 * 0.5);

  const applySuite = (value: string) => {
    setSuite(value);
    if (value === "pilot-smoke") {
      setSelected(["banking-pilot-001", "orders-pilot-001", "shipping-pilot-001", "payroll-pilot-001", "clinic-pilot-001"]);
      return;
    }
    if (value === "pilot-25") {
      setSelected(catalog.filter(item => item.scenario_id.includes("-pilot-")).map(item => item.scenario_id));
      return;
    }
    if (value === "benchmark-100") {
      setSelected(catalog.filter(item => item.scenario_id.includes("-benchmark-")).map(item => item.scenario_id));
      return;
    }
    if (value === "full-125") {
      setSelected(catalog.map(item => item.scenario_id));
      return;
    }
    setSelected([]);
  };

  const submit = async () => {
    if (!organizationId || !workspaceId || !selected.length) return;
    try {
      await createEvaluationJob({
        organization_id: organizationId,
        workspace_id: workspaceId,
        run_type: "selected_scenarios",
        run_name: runName,
        scenario_ids: selected,
        concurrency: 1,
        timeout_seconds: 600,
        judge_model: "gpt-4.1-mini",
        estimated_cost_usd: estimate,
        confirmed,
      });
      setOpen(false);
      setConfirmed(false);
      setNotice("Evaluation queued. Status refreshes automatically.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to queue evaluation.");
    }
  };

  const toggle = (id: string) => {
    setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  };

  const openReports = async (jobId: string) => {
    if (reportsByJob[jobId]) {
      setReportsByJob(current => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
      return;
    }
    setLoadingReports(jobId);
    try {
      const reports = await listEvaluationJobReports(jobId);
      setReportsByJob(current => ({ ...current, [jobId]: reports }));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load evaluation reports.");
    } finally {
      setLoadingReports("");
    }
  };

  return <section className="evaluation-job-control">
    <header className="evaluation-job-toolbar">
      <div>
        <p className="eyebrow">Evaluation execution</p>
        <h3>Run and monitor evaluations</h3>
        <p>Launch named suites or custom scenario sets, then monitor progress and regenerate reports.</p>
      </div>
      <div className="evaluation-job-toolbar-actions">
        <button onClick={() => void load()}>Refresh status</button>
        {canManage && <button className="primary" onClick={() => { setOpen(true); applySuite("pilot-smoke"); }}>Run evaluation</button>}
      </div>
    </header>

    {notice && <p className="form-message success" role="status">{notice}</p>}
    {error && <p className="form-message error" role="alert">{error}</p>}

    <div className="evaluation-job-list">
      {jobs.slice(0, 8).map(job => <article key={job.id} className="evaluation-job-item">
        <div className="evaluation-job-title-row">
          <div>
            <strong>{job.run_name}</strong>
            <small>{job.requested_by_email} · {job.completed_count} completed / {job.failed_count} failed</small>
          </div>
          <span className={`evaluation-status ${job.status}`}>{job.status.replaceAll("_", " ")}</span>
        </div>

        <div className="evaluation-job-progress-wrap">
          <progress max="100" value={job.progress_percentage} />
          <small>{job.current_scenario || "Waiting"} · {job.progress_percentage.toFixed(0)}%</small>
        </div>

        <div className="evaluation-job-actions">
          {isActive(job.status) && canManage && <button onClick={async () => { await cancelEvaluationJob(job.id); await load(); }}>Cancel</button>}
          {!isActive(job.status) && canManage && <button onClick={async () => { await retryEvaluationJob(job.id); await load(); }}>Re-run</button>}
          {job.evaluation_run_id && <button aria-expanded={Boolean(reportsByJob[job.id])} onClick={() => void openReports(job.id)}>{loadingReports === job.id ? "Loading reports..." : "Open reports"}</button>}
          {job.evaluation_run_id && canManage && <button onClick={async () => { const result = await regenerateEvaluationReports(job.id); setNotice(`Report regeneration ${result.status}.`); }}>Regenerate report</button>}
        </div>

        {reportsByJob[job.id] && <div className="evaluation-job-reports" aria-label={`Reports for ${job.run_name}`}>
          {reportsByJob[job.id].length
            ? reportsByJob[job.id].map(report => <a key={report.result_id} href={report.report_url}>{report.scenario_id} · {report.status}</a>)
            : <small>No scenario reports are available yet.</small>}
        </div>}
      </article>)}
    </div>

    {open && <div className="evaluation-modal-backdrop"><div className="evaluation-modal evaluation-catalog-modal" role="dialog" aria-modal="true" aria-labelledby="run-evaluation-title">
      <h2 id="run-evaluation-title">Run Evaluation</h2>
      <p>Select a named suite or build a targeted regression run. Ground truth remains server-side in the evaluation framework.</p>

      <div className="evaluation-form-grid">
        <label>Workspace<select value={workspaceId} onChange={event => setWorkspaceId(event.target.value)}>{spaces.map(space => <option key={space.id} value={space.id}>{space.name}</option>)}</select></label>
        <label>Named suite<select value={suite} onChange={event => applySuite(event.target.value)}><option value="pilot-smoke">Five-domain smoke</option><option value="pilot-25">Original pilot (25)</option><option value="benchmark-100">Regression benchmark (100)</option><option value="full-125">Full release validation (125)</option><option value="custom">Custom selection</option></select></label>
      </div>

      <label>Run name<input value={runName} onChange={event => setRunName(event.target.value)} /></label>

      <div className="evaluation-catalog-filters">
        <input aria-label="Search scenarios" placeholder="Search ID or incident question" value={query} onChange={event => setQuery(event.target.value)} />
        <select aria-label="Filter by domain" value={domain} onChange={event => setDomain(event.target.value)}><option value="all">All domains</option>{domains.map(value => <option key={value}>{value}</option>)}</select>
        <select aria-label="Filter by category" value={category} onChange={event => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map(value => <option key={value} value={value}>{titleCase(value)}</option>)}</select>
        <select aria-label="Filter by difficulty" value={difficulty} onChange={event => setDifficulty(event.target.value)}><option value="all">All difficulties</option>{["easy", "medium", "hard", "expert"].map(value => <option key={value} value={value}>{titleCase(value)}</option>)}</select>
      </div>

      <div className="evaluation-selection-summary">
        <strong>{selected.length} scenario(s) selected</strong>
        <small>Estimated duration {(durationSeconds / 60).toFixed(1)} minutes · Estimated cost ${estimate.toFixed(2)} · Tokens {estimatedTokens.toLocaleString()}</small>
        <label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /> Confirm immutable benchmark run and estimated cost.</label>
      </div>

      <div className="evaluation-catalog-grid">
        <div className="evaluation-catalog-list" role="listbox" aria-label="Scenario catalog">
          {filtered.map(item => <button key={item.scenario_id} type="button" className={selected.includes(item.scenario_id) ? "selected" : ""} onClick={() => { toggle(item.scenario_id); setPreview(item); }}><input type="checkbox" readOnly checked={selected.includes(item.scenario_id)} /><span>{item.scenario_id}</span><small>{item.domain} · {titleCase(item.category)} · {titleCase(item.difficulty)}</small></button>)}
        </div>
        <aside>{preview ? <><h4>{preview.scenario_id}</h4><p>{preview.question}</p><small>{preview.business_description || "No additional business context."}</small></> : <p>Select a scenario to preview its question and business context.</p>}</aside>
      </div>

      <div className="evaluation-modal-actions">
        <button onClick={() => setOpen(false)}>Cancel</button>
        <button className="primary" disabled={!selected.length || !confirmed || !runName.trim()} onClick={() => void submit()}>Queue evaluation</button>
      </div>
    </div></div>}
  </section>;
}
