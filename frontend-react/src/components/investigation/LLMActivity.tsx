import { useEffect, useState } from "react";
import { getInvestigationLLMActivity } from "../../api/llm-audit-api";
import type { LLMInvocationSummary } from "../../models/llm-audit";

export function LLMActivity({ investigationId }: { investigationId: string }) {
  const [items, setItems] = useState<LLMInvocationSummary[]>([]);
  const [message, setMessage] = useState("Loading LLM activity…");
  useEffect(() => {
    getInvestigationLLMActivity(investigationId)
      .then((result) => {
        if (!result) { setMessage("LLM activity could not be loaded."); return; }
        setItems(result.items);
        setMessage(result.zero_invocation_explanation
          ? `${result.zero_invocation_explanation.code}: ${result.zero_invocation_explanation.reason}`
          : result.message ?? "");
      })
      .catch(() => setMessage("LLM activity could not be loaded."));
  }, [investigationId]);
  return <details className="technical-details">
    <summary>LLM Activity ({items.length})</summary>
    {message && <p>{message}</p>}
    <ol>{items.map((item) => <li key={item.llm_invocation_id}>
      <strong>{item.stage_name}</strong> — {item.status}<br />
      {item.provider} / {item.model_name} · {item.duration_ms ?? "—"} ms ·
      {" "}{item.prompt_tokens} input / {item.completion_tokens} output · attempt {item.retry_attempt}
    </li>)}</ol>
  </details>;
}
