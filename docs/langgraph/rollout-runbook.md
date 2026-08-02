# LangGraph deployment runbook

LangGraph is enabled for 100% of requests in every environment. There are no allowlist,
percentage-cohort, shadow, compare, kill-switch, or Legacy fallback phases.

Before deployment, confirm the full regression suite, protected benchmark validation, graph
composition readiness, authorization, SQL safety, evidence integrity, report validation,
provider auditing, and operational ownership. After deployment, verify `/health`, `/ready`, an
end-to-end investigation, and persisted metadata (`LangGraph`, `LANGGRAPH`, graph version, and a
graph execution ID).

If validation fails, stop traffic or restore the prior LangGraph-only revision. Preserve all
investigation and audit artifacts for incident analysis.
