import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { getLLMInvocation, listLLMInvocations, type AuditFilters } from "../../api/llm-audit-api";
import type { LLMInvocationDetail, LLMInvocationSummary, ZeroInvocationExplanation } from "../../models/llm-audit";
import { EmptyState, SkeletonLoader } from "../../components/ui";

const codeSections: Array<[keyof LLMInvocationDetail, string]> = [
  ["system_prompt_sanitized", "System Prompt"], ["user_prompt_sanitized", "User Prompt"],
  ["context_payload_sanitized", "Request Context"], ["tool_definitions_sanitized", "Tool Definitions"],
  ["response_text_sanitized", "Response"],
];
const PAGE_SIZES = [10, 25, 50, 100];

function readablePrompt(value: unknown) {
  const text = String(value ?? "");
  if (!text) return "No content was recorded for this section.";
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; }
}
function statusLabel(status: string) {
  const labels: Record<string, string> = {
    completed: "Completed", failed: "Provider Error", timeout: "Timed Out", timed_out: "Timed Out",
    cancelled: "Blocked", rate_limited: "Provider Error", skipped_by_evidence_gate: "Skipped by Evidence Gate",
    blocked: "Blocked",
  };
  return labels[status.toLowerCase()] ?? status.replace(/_/g, " ");
}
function AuditStatusBadge({ status }: { status: string }) {
  return <span className="audit-status" data-status={status.toLowerCase()}><span aria-hidden="true">●</span>{statusLabel(status)}</span>;
}

function PromptDetailDialog({ detail, onClose }: { detail: LLMInvocationDetail; onClose: () => void }) {
  const [activeSection, setActiveSection] = useState<keyof LLMInvocationDetail>("system_prompt_sanitized");
  const closeRef = useRef<HTMLButtonElement>(null); const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const controls = [...(dialogRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled)") ?? [])];
      if (!controls.length) return;
      if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls.at(-1)?.focus(); }
      if (!event.shiftKey && document.activeElement === controls.at(-1)) { event.preventDefault(); controls[0].focus(); }
    };
    document.addEventListener("keydown", onKeyDown); return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);
  const label = codeSections.find(([key]) => key === activeSection)?.[1] ?? "Error";
  return <div className="audit-prompt-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section ref={dialogRef} className="audit-prompt-dialog" role="dialog" aria-modal="true" aria-labelledby="audit-prompt-title">
      <header><div><p className="eyebrow">Sanitized · read-only details</p><h2 id="audit-prompt-title">{detail.stage_name}</h2>
        <p>{detail.investigation_id ?? "No investigation"} · {detail.provider} / {detail.model_name}</p></div>
        <button ref={closeRef} className="icon-button" aria-label="Close invocation details" onClick={onClose}>×</button></header>
      <dl className="audit-prompt-metadata">
        <div><dt>Status</dt><dd><AuditStatusBadge status={detail.status} /></dd></div>
        <div><dt>Tokens</dt><dd>{detail.prompt_tokens} input · {detail.completion_tokens} output</dd></div>
        <div><dt>Duration</dt><dd>{detail.duration_ms == null ? "—" : `${detail.duration_ms} ms`}</dd></div>
        <div><dt>Trace</dt><dd>{detail.trace_id ?? detail.correlation_id ?? "—"}</dd></div>
        <div><dt>Environment</dt><dd>{detail.environment_type ?? "production"}</dd></div>
        <div><dt>Policy</dt><dd>{detail.policy_name ?? "production_strict"}</dd></div>
        <div><dt>Started</dt><dd>{new Date(detail.started_at).toLocaleString()}</dd></div>
        <div><dt>Skip / error reason</dt><dd>{detail.error_message_sanitized || "—"}</dd></div>
      </dl>
      <p className="redaction-notice">{detail.redaction_notice}</p>
      <nav className="audit-prompt-tabs" aria-label="Invocation detail sections">{codeSections.map(([key, text]) =>
        <button key={key} type="button" aria-pressed={activeSection === key} onClick={() => setActiveSection(key)}>{text}</button>)}
        {detail.error_message_sanitized && <button type="button" aria-pressed={activeSection === "error_message_sanitized"} onClick={() => setActiveSection("error_message_sanitized")}>Error</button>}
      </nav>
      <section className="audit-prompt-content" aria-live="polite" aria-label={label}><div><h3>{label}</h3><span>Sanitized · read only</span></div>
        <pre tabIndex={0}><code>{readablePrompt(detail[activeSection])}</code></pre></section>
    </section>
  </div>;
}

export function LLMInvocationAuditPage() {
  const initial: AuditFilters = { page: 1, page_size: 25, sort_by: "started_at", sort_direction: "desc" };
  const [draft, setDraft] = useState<AuditFilters>(initial); const [filters, setFilters] = useState<AuditFilters>(initial);
  const [items, setItems] = useState<LLMInvocationSummary[]>([]); const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0); const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<LLMInvocationDetail | null>(null); const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);
  const [error, setError] = useState(""); const [zeroExplanation, setZeroExplanation] = useState<ZeroInvocationExplanation | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const result = await listLLMInvocations(filters, signal);
      if (!result) throw new Error("The audit service returned no data.");
      if (result.total_pages > 0 && Number(filters.page) > result.total_pages) {
        setFilters((current) => ({ ...current, page: result.total_pages }));
        return;
      }
      setItems(result.items); setTotal(result.total_items ?? result.total); setTotalPages(result.total_pages ?? Math.ceil(result.total / result.page_size));
      setZeroExplanation(result.zero_invocation_explanation); setError("");
    } catch (cause) {
      if ((cause as { name?: string })?.name !== "AbortError") setError(cause instanceof Error ? cause.message : "Unable to load audit records.");
    } finally { if (!signal?.aborted) setLoading(false); }
  }, [filters]);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);

  const apply = (event: FormEvent) => { event.preventDefault(); setFilters({ ...draft, page: 1 }); };
  const clear = () => { setDraft(initial); setFilters(initial); };
  const movePage = (page: number) => setFilters((current) => ({ ...current, page }));
  const sort = (column: string) => setFilters((current) => ({
    ...current, page: 1, sort_by: column,
    sort_direction: current.sort_by === column && current.sort_direction === "asc" ? "desc" : "asc",
  }));
  const openDetail = async (item: LLMInvocationSummary) => {
    setDetailLoadingId(item.llm_invocation_id); setError("");
    try { const selected = await getLLMInvocation(item.llm_invocation_id); if (!selected) throw new Error("Invocation details were not returned."); setDetail(selected); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load invocation details."); }
    finally { setDetailLoadingId(null); }
  };
  const SortHeader = ({ column, children }: { column: string; children: string }) =>
    <th scope="col" aria-sort={filters.sort_by === column ? (filters.sort_direction === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" className="audit-sort" onClick={() => sort(column)} aria-label={`Sort by ${children}`}>
        {children}{filters.sort_by === column ? (filters.sort_direction === "asc" ? " ↑" : " ↓") : ""}
      </button>
    </th>;

  return <main className="page-shell audit-page">
    <header className="audit-page-header"><div><p className="eyebrow">Administration</p><h1>LLM Invocation Audit</h1>
      <p>Sanitized, read-only provider-call history for operational review and compliance.</p></div>
      <button className="ui-button ui-button-secondary" type="button" onClick={() => void load()} disabled={loading} aria-label="Refresh audit records">{loading ? "Refreshing…" : "Refresh"}</button></header>
    <form className="audit-filter-panel" onSubmit={apply}>
      <label>Investigation ID<input value={draft.investigation_id ?? ""} onChange={(e) => setDraft({ ...draft, investigation_id: e.target.value })} /></label>
      <label>Status<select value={draft.status ?? ""} onChange={(e) => setDraft({ ...draft, status: e.target.value })}><option value="">All statuses</option><option value="completed">Completed</option><option value="failed">Failed</option><option value="timeout">Timed out</option><option value="skipped_by_evidence_gate">Skipped by evidence gate</option><option value="blocked">Blocked</option></select></label>
      <label>Provider<input value={draft.provider ?? ""} onChange={(e) => setDraft({ ...draft, provider: e.target.value })} /></label>
      <label>Model<input value={draft.model ?? ""} onChange={(e) => setDraft({ ...draft, model: e.target.value })} /></label>
      <label>Invocation stage<input aria-label="Stage" value={draft.stage_name ?? ""} onChange={(e) => setDraft({ ...draft, stage_name: e.target.value })} /></label>
      <label>Prompt search<input aria-label="Search sanitized prompts" value={draft.search ?? ""} onChange={(e) => setDraft({ ...draft, search: e.target.value })} /></label>
      <label>From<input aria-label="From date and time" type="datetime-local" onChange={(e) => setDraft({ ...draft, started_after: e.target.value ? new Date(e.target.value).toISOString() : undefined })} /></label>
      <label>To<input aria-label="To date and time" type="datetime-local" onChange={(e) => setDraft({ ...draft, started_before: e.target.value ? new Date(e.target.value).toISOString() : undefined })} /></label>
      <label className="audit-checkbox"><input type="checkbox" checked={Boolean(draft.failed_only)} onChange={(e) => setDraft({ ...draft, failed_only: e.target.checked })} />Failed calls only</label>
      <div className="audit-filter-actions"><button className="ui-button ui-button-primary" type="submit">Apply filters</button><button className="ui-button ui-button-secondary" type="button" onClick={clear}>Clear filters</button></div>
    </form>
    {error && <div className="ui-alert" role="alert"><strong>Audit records could not be loaded</strong><span>{error}</span><button type="button" onClick={() => void load()}>Try again</button></div>}
    <div className="audit-grid-toolbar"><p><span>{total.toLocaleString()} invocation{total === 1 ? "" : "s"}</span> · Page {filters.page} of {Math.max(totalPages, 1)}</p>
      <label>Rows per page <select aria-label="Rows per page" value={filters.page_size} onChange={(e) => {
        const page_size = Number(e.target.value); setDraft((value) => ({ ...value, page_size })); setFilters((value) => ({ ...value, page: 1, page_size }));
      }}>{PAGE_SIZES.map((size) => <option key={size}>{size}</option>)}</select></label></div>
    {zeroExplanation && !loading && <section className="redaction-notice" aria-label="Why the LLM was not invoked"><strong>{zeroExplanation.code}</strong><p>{zeroExplanation.reason}</p></section>}
    {loading ? <SkeletonLoader label="Loading audit records" lines={8} /> : items.length === 0
      ? <EmptyState title="No invocation records" message="No audit records match the current filters." />
      : <div className="audit-grid-scroll" role="region" aria-label="LLM invocation audit records" tabIndex={0}><table className="audit-grid"><thead><tr>
        <SortHeader column="started_at">Timestamp</SortHeader><SortHeader column="investigation_id">Investigation ID</SortHeader>
        <th scope="col">Workspace / Database</th><SortHeader column="provider">Provider</SortHeader><SortHeader column="model">Model</SortHeader>
        <SortHeader column="stage_name">Invocation Stage</SortHeader><SortHeader column="status">Status</SortHeader>
        <th scope="col">Reason / Skip Reason</th><th scope="col">Prompt Preview</th><SortHeader column="prompt_tokens">Input Tokens</SortHeader>
        <SortHeader column="completion_tokens">Output Tokens</SortHeader><SortHeader column="duration_ms">Duration</SortHeader>
        <SortHeader column="estimated_cost">Cost</SortHeader><th scope="col">Actions</th>
      </tr></thead><tbody>{items.map((item) => <tr key={item.llm_invocation_id}>
        <td>{new Date(item.started_at).toLocaleString()}</td><td><code>{item.investigation_id ?? "—"}</code></td>
        <td>{item.workspace_name ?? item.workspace_id ?? "—"}<small>{item.database_name ?? item.connection_id ?? "Database unavailable"}</small></td><td>{item.provider}</td><td>{item.model_name}</td>
        <td>{item.stage_name}</td><td><AuditStatusBadge status={item.status} /></td><td className="audit-truncate" title={item.reason ?? ""}>{item.reason ?? "—"}</td>
        <td className="audit-prompt-preview" title={item.prompt_preview ?? ""}>{item.prompt_preview || "No prompt preview"}</td>
        <td>{item.prompt_tokens.toLocaleString()}</td><td>{item.completion_tokens.toLocaleString()}</td><td>{item.duration_ms == null ? "—" : `${item.duration_ms} ms`}</td>
        <td>{item.estimated_cost == null ? "—" : `${item.currency} ${item.estimated_cost}`}</td><td><button className="audit-view-prompt" type="button" aria-label="View prompt" disabled={detailLoadingId === item.llm_invocation_id} onClick={() => void openDetail(item)}>{detailLoadingId === item.llm_invocation_id ? "Loading…" : "View details"}</button></td>
      </tr>)}</tbody></table></div>}
    <nav className="audit-pagination" aria-label="Audit pagination"><button className="ui-button ui-button-secondary" type="button" disabled={loading || Number(filters.page) <= 1} onClick={() => movePage(Number(filters.page) - 1)}>Previous</button>
      <span>Page {filters.page} of {Math.max(totalPages, 1)}</span><button className="ui-button ui-button-secondary" type="button" disabled={loading || Number(filters.page) >= totalPages} onClick={() => movePage(Number(filters.page) + 1)}>Next</button></nav>
    {detail && <PromptDetailDialog detail={detail} onClose={() => setDetail(null)} />}
  </main>;
}
