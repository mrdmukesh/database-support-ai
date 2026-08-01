# LangGraph rollback runbook

## Immediate rollback

Set:

```text
LANGGRAPH_KILL_SWITCH=true
LANGGRAPH_ENABLED=false
INVESTIGATION_ORCHESTRATOR_MODE=LEGACY
LANGGRAPH_SHADOW_PERCENT=0
LANGGRAPH_ROLLOUT_PERCENT=0
LANGGRAPH_SHADOW_LLM_ENABLED=false
```

The kill switch is checked for every new request. Environment-backed configuration requires the
normal application restart/redeployment to refresh; active investigations are not forcibly
terminated. Do not delete their evidence, reports, comparisons, or invocation audits.

## Verification

Verify effective-runtime diagnostics show legacy, disabled, zero percentages, and active kill
switch. Confirm no new LangGraph/shadow/compare events, then run an authorized legacy smoke
investigation and validate the unchanged API response, read-only SQL controls, evidence audit,
and report retrieval.

Identify affected correlation IDs, selected results, failure stages, provider invocations, and
fallback attempts. Preserve all artifacts. Open an incident for safety, authorization,
evidence-loss, audit, or user-visible failures; otherwise open a defect and attach metrics and
comparison records.

No migration was added by LG-08, so database downgrade is unnecessary. Code rollback is secondary
and must target the last reviewed production commit.

LG-10 rollback baseline captured on 2026-07-31:

- commit/image tag: `47dad9433529c5232165e92b232c4eb68084a284`
- image digest:
  `sha256:85a34cac69b6c696c0ad83f7f09c38b53ed886d123539f3f4bca402dcb171a8f`
- Azure revision: `ca-database-support-ai-dev--0000154`
- control-database migration: `0021`

Restore the immutable image and legacy configuration:

```powershell
az containerapp update --name ca-database-support-ai-dev `
  --resource-group rg-database-support-ai-dev `
  --image ghcr.io/mrdmukesh/legacydb-support-copilot@sha256:85a34cac69b6c696c0ad83f7f09c38b53ed886d123539f3f4bca402dcb171a8f `
  --set-env-vars INVESTIGATION_ORCHESTRATOR_MODE=LEGACY LANGGRAPH_ENABLED=false `
    LANGGRAPH_ROLLOUT_PERCENT=0 LANGGRAPH_SHADOW_PERCENT=0 `
    LANGGRAPH_SHADOW_LLM_ENABLED=false LLM_REASONING_MODEL=gpt-4.1-mini
```

No LG-10 migration was added. Never apply control migrations to protected evaluation databases.

Communication template: “LangGraph traffic was disabled at `<time>` for `<reason>`. Legacy
investigations remain available. `<count>` requests are under review. Evidence and audit records
were preserved. Next update: `<time>`.”

Reactivation requires root-cause correction, complete regression and protected benchmark
evidence, zero critical gates, verified kill switch/fallback, operational approval, and restart
from rollout Phase 1 or the last explicitly approved phase.
