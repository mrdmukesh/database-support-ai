# LangGraph rollout runbook

## Prerequisites

Confirm the full regression suite, protected manifest validation, lower-environment benchmark,
zero critical release gates, graph composition health, kill switch, legacy fallback, monitoring
ownership, and change approval. Record application commit, graph version, environment, approved
workspace scope, query/load budget, provider-cost budget, and incident owner. Never place
credentials or allowlist values in rollout evidence.

## Phases

1. Phase 0 — deploy with `LANGGRAPH_ENABLED=false`, mode `LEGACY`, rollout 0, shadow 0.
2. Phase 1 — lower-environment `SHADOW` at 100%, shadow LLM off. Compare discovery, SQL safety,
   evidence semantics, coverage, load, latency, cancellation, and terminal status.
3. Phase 2 — authorized lower-environment `COMPARE`, shadow LLM on only with cost approval.
4. Phase 3 — approved production workspaces, 1–5% shadow, shadow LLM off.
5. Phase 4 — low production shadow reasoning only after audit/cost approval.
6. Phase 5 — 1% LangGraph primary pilot with safe fallback.
7. Phase 6 — reviewed expansion through 5%, 10%, 25%, 50%, and 100%.
8. Phase 7 — retain the legacy orchestrator, kill switch, and rollback path.

Each phase needs named engineering, DBA, security, product, and incident owners; CAB/change ticket;
start/end window; user communication; and explicit approval to advance.

## Validation and monitoring

At every phase confirm mode/commit/health, authorization, mutation/procedure count (must be zero),
query counts, timeouts, row-limit enforcement, evidence loss, NULL/no-row mismatches, Evidence
Gate decisions, provider/audit parity, unsupported claims, report validation, fallback success,
cancellation, p50/p95 latency, database load, tokens/cost, and comparison persistence.

Hold or roll back for any critical safety finding, authorization mismatch, evidence loss,
uncaught hallucination, audit gap, API incompatibility, fallback failure, secret exposure,
no-progress loop, material coverage regression, provider failure spike, or load/cost/latency above
the approved tolerance.

Production deployment never changes flags automatically. A protected benchmark is selected with
`python -m evaluation.cli run --suite research-25 --orchestrator langgraph`; the API environment
must already be authorized and configured for the candidate. Validate the recorded orchestrator
metadata before accepting results.

The runner enforces this against `/health` and stops before creating a run on a mode mismatch or
missing LangGraph composition. Run `/ready` first and accept only HTTP 200 with `status=ready`.

Post-rollout, verify one authorized request and one non-cohort request, confirm exactly one
user-visible response, inspect audit/evidence correlation, and retain comparison artifacts under
existing access and retention policy.
