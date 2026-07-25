import { FormEvent, useEffect, useState } from "react";
import { getLLMInvocation, listLLMInvocations, type AuditFilters } from "../../api/llm-audit-api";
import type { LLMInvocationDetail, LLMInvocationSummary } from "../../models/llm-audit";

const codeSections: Array<[keyof LLMInvocationDetail, string]> = [
  ["system_prompt_sanitized", "System Prompt"],
  ["user_prompt_sanitized", "User Prompt"],
  ["context_payload_sanitized", "Context"],
  ["tool_definitions_sanitized", "Tool Definitions"],
  ["response_text_sanitized", "Response"],
];

export function LLMInvocationAuditPage() {
  const [items, setItems] = useState<LLMInvocationSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<AuditFilters>({ page: 1, page_size: 25 });
  const [detail, setDetail] = useState<LLMInvocationDetail | null>(null);
  const [error, setError] = useState("");

  const load = async (next = filters) => {
    try {
      const result = await listLLMInvocations(next);
      if (!result) throw new Error("The audit service returned no data.");
      setItems(result.items); setTotal(result.total); setError("");
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

  return (
    <main className="page-shell">
      <header><p className="eyebrow">Administration</p><h1>LLM Invocation Audit</h1>
        <p>Read-only, sanitized provider-call history. Prompts cannot be edited, retried, or replayed.</p></header>
      <form className="filter-grid" onSubmit={submit}>
        <input aria-label="Investigation ID" placeholder="Investigation ID" onChange={(e) => setFilters({ ...filters, investigation_id: e.target.value })} />
        <input aria-label="Stage" placeholder="Stage" onChange={(e) => setFilters({ ...filters, stage_name: e.target.value })} />
        <input aria-label="Model" placeholder="Model" onChange={(e) => setFilters({ ...filters, model: e.target.value })} />
        <select aria-label="Status" onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          <option value="">All statuses</option><option>completed</option><option>failed</option>
          <option>timeout</option><option>rate_limited</option><option>cancelled</option>
        </select>
        <input aria-label="Search sanitized prompts" placeholder="Search sanitized prompts" onChange={(e) => setFilters({ ...filters, search: e.target.value })} />
        <label><input type="checkbox" onChange={(e) => setFilters({ ...filters, failed_only: e.target.checked })} /> Failed calls only</label>
        <button type="submit">Apply filters</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <p>{total} invocation{total === 1 ? "" : "s"}</p>
      <div className="table-scroll"><table><thead><tr>
        <th>Time</th><th>Investigation</th><th>Stage</th><th>Agent</th><th>Provider / Model</th>
        <th>Status</th><th>Tokens</th><th>Duration</th><th>Cost</th>
      </tr></thead><tbody>{items.map((item) => <tr key={item.llm_invocation_id}>
        <td><button className="link-button" onClick={async () => {
          const selected = await getLLMInvocation(item.llm_invocation_id);
          if (selected) setDetail(selected);
        }}>{new Date(item.started_at).toLocaleString()}</button></td>
        <td>{item.investigation_id ?? "—"}</td><td>{item.stage_name}</td><td>{item.agent_name}</td>
        <td>{item.provider} / {item.model_name}</td><td>{item.status}</td>
        <td>{item.prompt_tokens} / {item.completion_tokens} / {item.total_tokens}</td>
        <td>{item.duration_ms == null ? "—" : `${item.duration_ms} ms`}</td>
        <td>{item.estimated_cost == null ? "—" : `${item.currency} ${item.estimated_cost}`}</td>
      </tr>)}</tbody></table></div>
      {detail && <section className="audit-detail" aria-label="Invocation detail">
        <button onClick={() => setDetail(null)}>Close detail</button><h2>{detail.stage_name}</h2>
        <p><strong>Status:</strong> {detail.status} · <strong>Attempt:</strong> {detail.retry_attempt} · <strong>Correlation:</strong> {detail.correlation_id ?? "—"}</p>
        <p className="redaction-notice">{detail.redaction_notice}</p>
        {codeSections.map(([key, label]) => <details key={key} open={key === "system_prompt_sanitized"}>
          <summary>{label}</summary><pre><code>{String(detail[key] ?? "")}</code></pre>
        </details>)}
        {detail.error_message_sanitized && <details open><summary>Error</summary><pre>{detail.error_message_sanitized}</pre></details>}
      </section>}
    </main>
  );
}
