import { useEffect, useMemo, useState } from "react";
import { cancelEvaluationJob, createEvaluationJob, listEvaluationJobReports, listEvaluationJobs, regenerateEvaluationReports, retryEvaluationJob, type EvaluationJob, type EvaluationJobReport } from "../../api/evaluation-jobs-api";
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
    tags?: string[];
};
const catalog = catalogData as CatalogScenario[];
const active = (status: string) => ["queued", "preflight", "running", "cancelling"].includes(status);
const title = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
export function EvaluationJobControl() {
    const { organizationId, user } = useAuth();
    const [spaces, setSpaces] = useState<Workspace[]>([]), [jobs, setJobs] = useState<EvaluationJob[]>([]), [workspaceId, setWorkspaceId] = useState("");
    const [open, setOpen] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState(""), [runName, setRunName] = useState(`benchmark-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}`), [confirmed, setConfirmed] = useState(false);
    const [suite, setSuite] = useState("pilot-smoke"), [query, setQuery] = useState(""), [domain, setDomain] = useState("all"), [category, setCategory] = useState("all"), [difficulty, setDifficulty] = useState("all"), [selected, setSelected] = useState<string[]>([]), [preview, setPreview] = useState<CatalogScenario | null>(null);
    const [reportsByJob, setReportsByJob] = useState<Record<string, EvaluationJobReport[]>>({}), [loadingReports, setLoadingReports] = useState("");
    const canManage = ["super_admin", "organization_admin"].includes(user?.role ?? "");
    const load = async () => { if (!organizationId)
        return; try {
        const ws = await listWorkspaces(organizationId);
        setSpaces(ws);
        const chosen = workspaceId || ws[0]?.id || "";
        if (!workspaceId)
            setWorkspaceId(chosen);
        setJobs(await listEvaluationJobs(chosen || undefined));
        setError("");
    }
    catch (e) {
        setError(e instanceof Error ? e.message : "Unable to load evaluation jobs.");
    } };
    useEffect(() => { void load(); }, [organizationId, workspaceId]);
    useEffect(() => { if (!jobs.some(job => active(job.status)))
        return; const timer = setInterval(() => void load(), 3000); return () => clearInterval(timer); }, [jobs, workspaceId]);
    const categories = useMemo(() => [...new Set(catalog.map(item => item.category))].sort(), []);
    const filtered = useMemo(() => catalog.filter(item => (domain === "all" || item.domain === domain) && (category === "all" || item.category === category) && (difficulty === "all" || item.difficulty === difficulty) && (!query || `${item.scenario_id} ${item.question}`.toLowerCase().includes(query.toLowerCase()))), [query, domain, category, difficulty]);
    const chosen = useMemo(() => catalog.filter(item => selected.includes(item.scenario_id)), [selected]);
    const duration = chosen.reduce((sum, item) => sum + (item.estimated_duration_seconds || 60), 0), tokens = chosen.reduce((sum, item) => sum + (item.estimated_token_usage || 2000), 0), estimate = Math.max(.01, tokens / 1000000 * .5);
    const applySuite = (value: string) => { setSuite(value); if (value === "pilot-smoke")
        setSelected(["banking-pilot-001", "orders-pilot-001", "shipping-pilot-001", "payroll-pilot-001", "clinic-pilot-001"]);
    else if (value === "pilot-25")
        setSelected(catalog.filter(item => item.scenario_id.includes("-pilot-")).map(item => item.scenario_id));
    else if (value === "benchmark-100")
        setSelected(catalog.filter(item => item.scenario_id.includes("-benchmark-")).map(item => item.scenario_id));
    else if (value === "full-125")
        setSelected(catalog.map(item => item.scenario_id));
    else
        setSelected([]); };
    const submit = async () => { if (!organizationId || !workspaceId || !selected.length)
        return; try {
        await createEvaluationJob({ organization_id: organizationId, workspace_id: workspaceId, run_type: "selected_scenarios", run_name: runName, scenario_ids: selected, concurrency: 1, timeout_seconds: 600, judge_model: "gpt-4.1-mini", estimated_cost_usd: estimate, confirmed });
        setOpen(false);
        setConfirmed(false);
        setNotice("Evaluation queued. Status refreshes automatically.");
        await load();
    }
    catch (e) {
        setError(e instanceof Error ? e.message : "Unable to queue evaluation.");
    } };
    const toggle = (id: string) => setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
    const openReports = async (jobId: string) => {
        if (reportsByJob[jobId]) {
            setReportsByJob(current => { const next = { ...current }; delete next[jobId]; return next; });
            return;
        }
        setLoadingReports(jobId);
        try {
            const reports = await listEvaluationJobReports(jobId);
            setReportsByJob(current => ({ ...current, [jobId]: reports }));
            setError("");
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unable to load evaluation reports.");
        } finally {
            setLoadingReports("");
        }
    };
    return <section className="evaluation-job-control"><div className="evaluation-job-toolbar"><div><h3>Evaluation execution</h3><p>Run named suites or select from 125 validated read-only investigation scenarios.</p></div><div><button onClick={() => void load()}>Refresh status</button>{canManage && <button className="primary" onClick={() => { setOpen(true); applySuite("pilot-smoke"); }}>Run Evaluation</button>}</div></div>{notice && <p className="form-message success">{notice}</p>}{error && <p className="form-message error" role="alert">{error}</p>}<div className="evaluation-job-list">{jobs.slice(0, 8).map(job => <article key={job.id}><div><strong>{job.run_name}</strong> <span className={`evaluation-status ${job.status}`}>{job.status.replaceAll("_", " ")}</span><small>{job.requested_by_email} · {job.completed_count} completed / {job.failed_count} failed</small></div><div><progress max="100" value={job.progress_percentage}/><small>{job.current_scenario || "Waiting"} · {job.progress_percentage.toFixed(0)}%</small></div><div className="evaluation-job-actions">{active(job.status) && canManage && <button onClick={async () => { await cancelEvaluationJob(job.id); await load(); }}>Cancel</button>}{!active(job.status) && canManage && <button onClick={async () => { await retryEvaluationJob(job.id); await load(); }}>Re-run</button>}{job.evaluation_run_id && <button aria-expanded={Boolean(reportsByJob[job.id])} onClick={() => void openReports(job.id)}>{loadingReports === job.id ? "Loading reports…" : "Open reports"}</button>}{job.evaluation_run_id && canManage && <button onClick={async () => { const result = await regenerateEvaluationReports(job.id); setNotice(`Report regeneration ${result.status}.`); }}>Regenerate Report</button>}</div>{reportsByJob[job.id] && <div className="evaluation-job-reports" aria-label={`Reports for ${job.run_name}`}>{reportsByJob[job.id].length ? reportsByJob[job.id].map(report => <a key={report.result_id} href={report.report_url}>{report.scenario_id} <span className={`evaluation-status ${report.status}`}>{report.status.replaceAll("_", " ")}</span></a>) : <p>No scenario reports are available for this run.</p>}</div>}</article>)}</div>
  {open && <div className="evaluation-modal-backdrop"><div className="evaluation-modal evaluation-catalog-modal" role="dialog" aria-modal="true" aria-labelledby="run-evaluation-title"><h2 id="run-evaluation-title">Run Evaluation</h2><p>Select a named suite or build a targeted regression run. Ground truth remains server-side in the evaluation framework.</p><div className="evaluation-form-grid"><label>Workspace<select value={workspaceId} onChange={event => setWorkspaceId(event.target.value)}>{spaces.map(space => <option key={space.id} value={space.id}>{space.name}</option>)}</select></label><label>Named suite<select value={suite} onChange={event => applySuite(event.target.value)}><option value="pilot-smoke">Five-domain smoke</option><option value="pilot-25">Original pilot (25)</option><option value="benchmark-100">Regression benchmark (100)</option><option value="full-125">Full release validation (125)</option><option value="custom">Custom selection</option></select></label></div><label>Run name<input value={runName} onChange={event => setRunName(event.target.value)}/></label><div className="evaluation-catalog-filters"><input aria-label="Search scenarios" placeholder="Search ID or incident question" value={query} onChange={event => setQuery(event.target.value)}/><select aria-label="Filter by domain" value={domain} onChange={event => setDomain(event.target.value)}><option value="all">All domains</option>{[...new Set(catalog.map(item => item.domain))].map(value => <option key={value}>{value}</option>)}</select><select aria-label="Filter by category" value={category} onChange={event => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map(value => <option key={value} value={value}>{title(value)}</option>)}</select><select aria-label="Filter by difficulty" value={difficulty} onChange={event => setDifficulty(event.target.value)}><option value="all">All difficulties</option>{["easy", "medium", "hard", "expert"].map(value => <option key={value}>{value}</option>)}</select></div><div className="evaluation-selection-toolbar"><span>{selected.length} selected · ~{Math.ceil(duration / 60)} min · {tokens.toLocaleString()} tokens · ${estimate.toFixed(2)}</span><button onClick={() => { setSuite("custom"); setSelected([...new Set([...selected, ...filtered.map(item => item.scenario_id)])]); }}>Select filtered</button><button onClick={() => { setSuite("custom"); setSelected([]); }}>Clear</button></div><div className="evaluation-catalog-list" role="list">{filtered.map(item => <div role="listitem" key={item.scenario_id}><label><input type="checkbox" checked={selected.includes(item.scenario_id)} onChange={() => { setSuite("custom"); toggle(item.scenario_id); }}/><span><strong>{item.scenario_id}</strong><small>{title(item.domain)} · {title(item.category)} · {title(item.difficulty)}</small></span></label><button aria-label={`Preview ${item.scenario_id}`} onClick={() => setPreview(item)}>Preview</button></div>)}</div>{preview && <aside className="evaluation-scenario-preview"><button aria-label="Close preview" onClick={() => setPreview(null)}>×</button><h3>{preview.scenario_id}</h3><p>{preview.question}</p><dl><dt>Domain</dt><dd>{title(preview.domain)}</dd><dt>Category</dt><dd>{title(preview.category)}</dd><dt>Difficulty</dt><dd>{title(preview.difficulty)}</dd><dt>Validation</dt><dd><span className="evaluation-status completed">Valid</span></dd></dl></aside>}<label className="evaluation-confirm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)}/>I confirm the estimated cost and immutable evidence snapshot.</label><div className="evaluation-modal-actions"><button onClick={() => setOpen(false)}>Cancel</button><button className="primary" disabled={!confirmed || !runName || !workspaceId || !selected.length} onClick={() => void submit()}>Start {selected.length} scenarios</button></div></div></div>}</section>;
}
