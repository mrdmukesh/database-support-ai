# Azure LangGraph deployment

All Azure revisions use LangGraph for every request. Workspace/user allowlists, percentage
cohorts, shadow/compare modes, kill switches, and workflow-engine fallback are retired.

```text
INVESTIGATION_ORCHESTRATOR_MODE=LANGGRAPH
LANGGRAPH_ENABLED=true
LANGGRAPH_MAX_CONCURRENT_RUNS=1
LANGGRAPH_FALLBACK_TO_LEGACY=false
LANGGRAPH_KILL_SWITCH=false
LANGGRAPH_ROLLOUT_PERCENT=100
LANGGRAPH_SHADOW_PERCENT=0
LANGGRAPH_SHADOW_LLM_ENABLED=false
```

Before accepting a revision, confirm `/health` reports an installed and compiled graph,
`LANGGRAPH` mode, and fallback disabled. Run authorization, bounded-concurrency, banking, and
payroll validations and verify persisted execution metadata contains a graph version and graph
execution ID.

Rollback is an application/image rollback to another LangGraph-only revision. Do not change
workflow settings to select a retired engine.
