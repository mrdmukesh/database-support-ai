import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { compareEvaluationRuns, deleteEvaluationRuns, getEvaluationSummary, listEvaluationRuns, listEvaluationScenarios, listHumanReviews } from "../../api/evaluation-api";
import type { EvaluationComparison, EvaluationRun, EvaluationScenario, EvaluationSummary } from "../../models/evaluation";
import { EvaluationJobControl } from "./EvaluationJobControl";

const score = (value:number|null) => value === null ? "Not scored" : value.toFixed(1);
const money = (value:number) => new Intl.NumberFormat("en-US", {style:"currency",currency:"USD",minimumFractionDigits:2,maximumFractionDigits:4}).format(value);

export function EvaluationDashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedRunId = searchParams.get("runId") ?? "";
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [runId, setRunId] = useState("");
  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [scenarios, setScenarios] = useState<EvaluationScenario[]>([]);
  const [reviews, setReviews] = useState<EvaluationScenario[]>([]);
  const [comparisonId, setComparisonId] = useState("");
  const [comparison, setComparison] = useState<EvaluationComparison | null>(null);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [view, setView] = useState<"results" | "reviews" | "comparison">("results");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const runById = useMemo(() => new Map(runs.map(item => [item.id, item])), [runs]);
  const deletableIds = useMemo(() => runs.filter(run => !run.is_protected).map(run => run.id), [runs]);
  const selectedNames = useMemo(() => selectedRunIds.map(id => runById.get(id)?.name || id), [selectedRunIds, runById]);

  const loadRuns = useCallback(async (signal?: AbortSignal) => {
    const rows = await listEvaluationRuns(signal);
    setRuns(rows);
    setSelectedRunIds(current => current.filter(id => rows.some(run => run.id === id && !run.is_protected)));
    setRunId(current => {
      if (rows.some(run => run.id === requestedRunId)) return requestedRunId;
      if (rows.some(run => run.id === current)) return current;
      return rows[0]?.id ?? "";
    });
  }, [requestedRunId]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    loadRuns(controller.signal)
      .catch(cause => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Unable to load evaluation runs.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [loadRuns]);

  useEffect(() => {
    if (!runId) {
      setSummary(null);
      setScenarios([]);
      setReviews([]);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    Promise.all([getEvaluationSummary(runId, controller.signal), listEvaluationScenarios(runId, controller.signal), listHumanReviews(runId, controller.signal)])
      .then(([summaryValue, scenarioRows, reviewRows]) => {
        setSummary(summaryValue);
        setScenarios(scenarioRows);
        setReviews(reviewRows);
        setComparisonId(current => current && current !== runId ? current : (runs.find(run => run.id !== runId)?.id ?? ""));
      })
      .catch(cause => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Unable to load evaluation results.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [runId, runs]);

  useEffect(() => {
    if (view !== "comparison" || !runId || !comparisonId) {
      setComparison(null);
      return;
    }
    const controller = new AbortController();
    compareEvaluationRuns(comparisonId, runId, controller.signal)
      .then(setComparison)
      .catch(cause => setError(cause instanceof Error ? cause.message : "Unable to compare runs."));
    return () => controller.abort();
  }, [view, runId, comparisonId]);

  const selectAll = () => setSelectedRunIds(deletableIds);
  const clearSelection = () => setSelectedRunIds([]);
  const toggleSelection = (id: string) => setSelectedRunIds(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);

  const removeSelected = async () => {
    if (!selectedRunIds.length || deleting) return;
    const label = `${selectedRunIds.length} selected run${selectedRunIds.length === 1 ? "" : "s"}`;
    const lines = selectedNames.slice(0, 10).map(name => `- ${name}`);
    const overflow = selectedNames.length > 10 ? `\n- ...and ${selectedNames.length - 10} more` : "";
    const confirmed = window.confirm(`Delete ${label}?\n\n${lines.join("\n")}${overflow}\n\nThis removes selected run records and associated evaluation results/reports. Protected runs will be skipped.`);
    if (!confirmed) return;

    setDeleting(true);
    setError("");
    setNotice("");
    try {
      const result = await deleteEvaluationRuns(selectedRunIds);
      const messages: string[] = [];
      if (result.deleted.length) messages.push(`Deleted ${result.deleted.length} run(s).`);
      if (result.protected.length) messages.push(`Skipped ${result.protected.length} protected run(s).`);
      if (result.missing.length) messages.push(`Skipped ${result.missing.length} unavailable run(s).`);
      setNotice(messages.join(" "));
      await loadRuns();
      setSearchParams(runId ? { runId } : {});
      clearSelection();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to delete selected runs.");
    } finally {
      setDeleting(false);
    }
  };

  if (loading && !runs.length) return <p>Loading evaluation dashboard…</p>;
  if (error && !runs.length) return <div className="form-message error" role="alert">{error}</div>;
  if (!runs.length) {
    return <section className="evaluation-page"><header><p className="eyebrow">Research evaluation</p><h2>Evaluation Dashboard</h2></header><EvaluationJobControl /><div className="evaluation-empty"><span aria-hidden="true">◎</span><h3>No completed evaluation runs yet</h3><p>Run the five-domain pilot smoke test, then the 25-scenario pilot. Persisted scores, timing, token usage, cost, and review flags will appear here automatically.</p></div></section>;
  }

  return <section className="evaluation-page" aria-labelledby="evaluation-title"><EvaluationJobControl />
    <header className="evaluation-heading"><div><p className="eyebrow">Research evaluation</p><h2 id="evaluation-title">Evaluation Dashboard</h2><p>Read-only pilot quality, safety, latency, and cost reporting.</p></div><label>Evaluation run<select aria-label="Evaluation run" value={runId} onChange={event => { const value = event.target.value; setRunId(value); setSearchParams(value ? { runId: value } : {}); }}>{runs.map(run => <option key={run.id} value={run.id}>{run.name} · {run.completed_count}/{run.scenario_count}</option>)}</select></label></header>

    <section className="evaluation-run-management" aria-label="Run management">
      <div className="evaluation-run-management-header"><h3>Manage persisted runs</h3><p>Select specific runs for deletion. Protected official/frozen/release benchmark runs are read-only.</p></div>
      <div className="evaluation-run-actions"><button type="button" onClick={selectAll} disabled={!deletableIds.length || deleting}>Select All</button><button type="button" onClick={clearSelection} disabled={!selectedRunIds.length || deleting}>Clear Selection</button><button type="button" className="danger" onClick={() => void removeSelected()} disabled={!selectedRunIds.length || deleting}>{deleting ? "Deleting..." : `Delete Selected (${selectedRunIds.length})`}</button></div>
      <div className="evaluation-run-grid">
        {runs.map(run => <article key={run.id} className="evaluation-run-item"><label><input type="checkbox" checked={selectedRunIds.includes(run.id)} disabled={Boolean(run.is_protected) || deleting} onChange={() => toggleSelection(run.id)} />
          <div><strong>{run.name}</strong><small>{new Date(run.created_at).toLocaleString()} · {run.completed_count}/{run.scenario_count}</small></div></label><div className="evaluation-run-meta"><span className={`evaluation-status ${run.status}`}>{run.status.replaceAll("_", " ")}</span>{run.is_protected ? <span className="evaluation-status protected" title={run.protection_reason || "Protected"}>Protected</span> : null}</div></article>)}
      </div>
    </section>

    {notice && <div className="form-message success" role="status">{notice}</div>}
    {error && <div className="form-message error" role="alert">{error}</div>}
    {summary && <><div className="evaluation-metrics">
      <article><span>Deterministic score</span><strong>{score(summary.deterministic_average)}</strong></article><article><span>AI judge score</span><strong>{score(summary.ai_judge_average)}</strong></article><article><span>Passed</span><strong>{summary.passed_count}/{summary.scenario_count}</strong></article><article><span>Human review</span><strong>{summary.human_review_count}</strong></article><article><span>Total duration</span><strong>{summary.total_duration_seconds.toFixed(1)}s</strong></article><article><span>Tokens / cost</span><strong>{summary.total_tokens.toLocaleString()}</strong><small>{money(summary.total_cost_usd)}</small></article>
    </div><div className="evaluation-breakdown"><div><h3>Coverage by domain</h3>{Object.entries(summary.domains).map(([name, count]) => <span key={name}><b>{name}</b>{count}</span>)}</div><div><h3>Execution status</h3>{Object.entries(summary.statuses).map(([name, count]) => <span key={name}><b>{name.replaceAll("_", " ")}</b>{count}</span>)}</div></div></>}
    <nav id="scenario-results" className="evaluation-tabs" aria-label="Evaluation views"><button className={view === "results" ? "active" : ""} onClick={() => setView("results")}>Scenario results</button><button className={view === "reviews" ? "active" : ""} onClick={() => setView("reviews")}>Human review <span>{reviews.length}</span></button><button className={view === "comparison" ? "active" : ""} onClick={() => setView("comparison")}>Compare runs</button></nav>
    {view === "results" && <ScenarioTable rows={scenarios} />} {view === "reviews" && (reviews.length ? <ScenarioTable rows={reviews} /> : <div className="evaluation-inline-empty"><h3>No scenarios require human review</h3><p>The latest validator and judge versions have no active review flags.</p></div>)}
    {view === "comparison" && <div className="evaluation-comparison"><label>Baseline run<select aria-label="Baseline run" value={comparisonId} onChange={event => setComparisonId(event.target.value)}><option value="">Select a run</option>{runs.filter(run => run.id !== runId).map(run => <option key={run.id} value={run.id}>{run.name}</option>)}</select></label>{comparison ? <table><thead><tr><th>Metric</th><th>Baseline</th><th>Selected run</th><th>Change</th></tr></thead><tbody>{[["Deterministic score", "deterministic_average"], ["AI judge score", "ai_judge_average"], ["Passed", "passed_count"], ["Human review", "human_review_count"], ["Duration (s)", "total_duration_seconds"], ["Tokens", "total_tokens"], ["Cost (USD)", "total_cost_usd"]].map(([label, key]) => <tr key={key}><th>{label}</th><td>{String(comparison.baseline[key as keyof EvaluationSummary] ?? "-")}</td><td>{String(comparison.candidate[key as keyof EvaluationSummary] ?? "-")}</td><td>{comparison.deltas[key] === null ? "-" : `${comparison.deltas[key]! > 0 ? "+" : ""}${comparison.deltas[key]}`}</td></tr>)}</tbody></table> : <p className="empty-state">Select a different persisted run to compare.</p>}</div>}
  </section>;
}

function ScenarioTable({rows}:{rows:EvaluationScenario[]}) { return <div className="evaluation-table-wrap"><table className="evaluation-table"><thead><tr><th>Scenario</th><th>Domain</th><th>Status</th><th>Deterministic</th><th>AI judge</th><th>Review</th><th>Duration</th><th>Cost</th></tr></thead><tbody>{rows.map(row=><tr key={row.result_id}><td><Link to={`/app/evaluation/scenarios/${row.result_id}`}>{row.scenario_id}</Link><small>v{row.scenario_version} · attempt {row.attempt}</small></td><td>{row.domain}</td><td><span className={`evaluation-status ${row.execution_status}`}>{row.execution_status.replaceAll("_"," ")}</span></td><td>{score(row.deterministic_score)}{row.critical_failure&&<small className="critical">Critical failure</small>}</td><td>{score(row.ai_judge_score)}</td><td>{row.human_review_required?"Required":"No"}</td><td>{row.duration_seconds.toFixed(1)}s</td><td>{money(row.cost_usd)}</td></tr>)}</tbody></table></div> }
