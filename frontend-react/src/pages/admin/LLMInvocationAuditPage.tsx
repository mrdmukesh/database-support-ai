import { FormEvent, useEffect, useRef, useState } from "react";
import { getLLMInvocation, listLLMInvocations, type AuditFilters } from "../../api/llm-audit-api";
import type { LLMInvocationDetail, LLMInvocationSummary, ZeroInvocationExplanation } from "../../models/llm-audit";

const codeSections: Array<[keyof LLMInvocationDetail, string]> = [
  ["system_prompt_sanitized", "System Prompt"],
  ["user_prompt_sanitized", "User Prompt"],
  ["context_payload_sanitized", "Request Context"],
  ["tool_definitions_sanitized", "Tool Definitions"],
  ["response_text_sanitized", "Response"],
];

function readablePrompt(value: unknown) {
  const text = String(value ?? "");
  if (!text) return "No content was recorded for this section.";
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function PromptDetailDialog({ detail, onClose }: { detail: LLMInvocationDetail; onClose: () => void }) {
  const [activeSection, setActiveSection] = useState<keyof LLMInvocationDetail>("system_prompt_sanitized");
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const focusable = [...(dialogRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled)") ?? [])];
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const activeLabel = codeSections.find(([key]) => key === activeSection)?.[1] ?? "Error";
  return <div className="audit-prompt-backdrop" role="presentation" onMouseDown={(event) => {
    if (event.currentTarget === event.target) onClose();
  }}>
    <section ref={dialogRef} className="audit-prompt-dialog" role="dialog" aria-modal="true" aria-labelledby="audit-prompt-title">
      <header>
        <div>
          <p className="eyebrow">Read-only prompt details</p>
          <h2 id="audit-prompt-title">{detail.stage_name}</h2>
          <p>{detail.agent_name} · {detail.provider} / {detail.model_name}</p>
        </div>
        <button ref={closeRef} className="icon-button" aria-label="Close prompt details" onClick={onClose}>×</button>
      </header>
      <dl className="audit-prompt-metadata">
        <div><dt>Status</dt><dd>{detail.status}</dd></div>
        <div><dt>Tokens</dt><dd>{detail.prompt_tokens} input · {detail.completion_tokens} output</dd></div>
        <div><dt>Duration</dt><dd>{detail.duration_ms == null ? "—" : `${detail.duration_ms} ms`}</dd></div>
        <div><dt>Attempt</dt><dd>{detail.retry_attempt}</dd></div>
      </dl>
      <p className="redaction-notice">{detail.redaction_notice}</p>
      <nav className="audit-prompt-tabs" aria-label="Prompt detail sections">
        {codeSections.map(([key, label]) => <button key={key} type="button"
          aria-pressed={activeSection === key} onClick={() => setActiveSection(key)}>
          {label}
        </button>)}
        {detail.error_message_sanitized && <button type="button"
          aria-pressed={activeSection === "error_message_sanitized"}
          onClick={() => setActiveSection("error_message_sanitized")}>Error</button>}
      </nav>
      <section className="audit-prompt-content" aria-live="polite" aria-label={activeLabel}>
        <div><h3>{activeLabel}</h3><span>Sanitized · read only</span></div>
        <pre tabIndex={0}><code>{readablePrompt(detail[activeSection])}</code></pre>
      </section>
    </section>
  </div>;
}

export function LLMInvocationAuditPage() {
  const [items, setItems] = useState<LLMInvocationSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<AuditFilters>({ page: 1, page_size: 25 });
  const [detail, setDetail] = useState<LLMInvocationDetail | null>(null);
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [zeroExplanation, setZeroExplanation] = useState<ZeroInvocationExplanation | null>(null);

  const load = async (next = filters) => {
    try {
      const result = await listLLMInvocations(next);
      if (!result) throw new Error("The audit service returned no data.");
      setItems(result.items); setTotal(result.total); setError("");
      setZeroExplanation(result.zero_invocation_explanation);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load audit records.");
    }
  };
  useEffect(() => { void load(); }, []); // initial read only

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const next = { ...filters, page: 1 };
    setFilters(next); void load(next);
  };

  const openDetail = async (item: LLMInvocationSummary) => {
    setDetailLoadingId(item.llm_invocation_id);
    setError("");
    try {
      const selected = await getLLMInvocation(item.llm_invocation_id);
      if (!selected) throw new Error("Prompt details were not returned.");
      setDetail(selected);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load prompt details.");
    } finally {
      setDetailLoadingId(null);
    }
  };

  return (
    <main className="page-shell">
      <header><p className="eyebrow">Administration</p><h1>LLM Invocation Audit</h1>
        <p>Read-only, sanitized provider-call history. Select <strong>View prompt</strong> to inspect exactly what was recorded for a call.</p></header>
      <form className="filter-grid" onSubmit={submit}>
        <input aria-label="Investigation ID" placeholder="Investigation ID" onChange={(e) => setFilters({ ...filters, investigation_id: e.target.value })} />
        <input aria-label="Stage" placeholder="Stage" onChange={(e) => setFilters({ ...filters, stage_name: e.target.value })} />
        <input aria-label="Model" placeholder="Model" onChange={(e) => setFilters({ ...filters, model: e.target.value })} />
        <select aria-label="Status" onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          <option value="">All statuses</option><option>completed</option><option>failed</option>
          <option>timeout</option><option>rate_limited</option><option>cancelled</option>
        </select>
        <input aria-label="Search sanitized prompts" placeholder="Search sanitized prompts" onChange={(e) => setFilters({ ...filters, search: e.target.value })} />
        <label>From <input aria-label="From date and time" type="datetime-local" onChange={(e) => setFilters({ ...filters, started_after: e.target.value ? new Date(e.target.value).toISOString() : undefined })} /></label>
        <label>To <input aria-label="To date and time" type="datetime-local" onChange={(e) => setFilters({ ...filters, started_before: e.target.value ? new Date(e.target.value).toISOString() : undefined })} /></label>
        <label><input type="checkbox" onChange={(e) => setFilters({ ...filters, failed_only: e.target.checked })} /> Failed calls only</label>
        <button type="submit">Apply filters</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <p>{total} invocation{total === 1 ? "" : "s"}</p>
      {zeroExplanation && <section className="redaction-notice" aria-label="Why the LLM was not invoked">
        <strong>{zeroExplanation.code}</strong><p>{zeroExplanation.reason}</p>
      </section>}
      <div className="table-scroll"><table><thead><tr>
        <th>Time</th><th>Investigation</th><th>Stage</th><th>Agent</th><th>Provider / Model</th>
        <th>Status</th><th>Tokens</th><th>Duration</th><th>Cost</th><th>Prompt details</th>
      </tr></thead><tbody>{items.map((item) => <tr key={item.llm_invocation_id}>
        <td>{new Date(item.started_at).toLocaleString()}</td>
        <td>{item.investigation_id ?? "—"}</td><td>{item.stage_name}</td><td>{item.agent_name}</td>
        <td>{item.provider} / {item.model_name}</td><td>{item.status}</td>
        <td>{item.prompt_tokens} / {item.completion_tokens} / {item.total_tokens}</td>
        <td>{item.duration_ms == null ? "—" : `${item.duration_ms} ms`}</td>
        <td>{item.estimated_cost == null ? "—" : `${item.currency} ${item.estimated_cost}`}</td>
        <td><button className="audit-view-prompt" type="button"
          disabled={detailLoadingId === item.llm_invocation_id}
          onClick={() => void openDetail(item)}>
          {detailLoadingId === item.llm_invocation_id ? "Loading…" : "View prompt"}
        </button></td>
      </tr>)}</tbody></table></div>
      {detail && <PromptDetailDialog detail={detail} onClose={() => setDetail(null)} />}
    </main>
  );
}
