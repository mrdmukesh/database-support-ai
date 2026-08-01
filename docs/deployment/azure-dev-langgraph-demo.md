# Azure dev LangGraph demo activation

## Scope and configuration

This activation applies only to the configured `azure-low-cost` GitHub environment and the
`ca-database-support-ai-dev` Container App. It does not change any production deployment target.
The allowlisted identifiers are stored as protected GitHub environment variables rather than in
source control:

- `LANGGRAPH_DEMO_WORKSPACE_ID`
- `LANGGRAPH_DEMO_USER_ID`

The deployment fails closed when either variable is absent. The Azure dev revision receives:

```text
INVESTIGATION_ORCHESTRATOR_MODE=LANGGRAPH
LANGGRAPH_ENABLED=true
LANGGRAPH_ALLOWED_ENVIRONMENTS=evaluation
LANGGRAPH_ALLOWED_WORKSPACE_IDS=<azure-low-cost protected variable>
LANGGRAPH_ALLOWED_USER_IDS=<azure-low-cost protected variable>
LANGGRAPH_MAX_CONCURRENT_RUNS=1
LANGGRAPH_FALLBACK_TO_LEGACY=true
LANGGRAPH_KILL_SWITCH=false
LANGGRAPH_ROLLOUT_PERCENT=0
LANGGRAPH_SHADOW_PERCENT=0
LANGGRAPH_SHADOW_LLM_ENABLED=false
```

Selection remains fail closed: the connection must resolve to the `evaluation` environment and
both the workspace and user must match. Everyone else remains on legacy. Global percentage
rollout is zero and must not be increased without explicit approval.

## Verification

Before accepting the demo revision:

1. Confirm `/health` reports installed, compiled, enabled, and `LANGGRAPH` mode.
2. Confirm `/ready` reports the graph composition, database, migration, and model provider ready.
3. Run authorization and non-allowlisted routing tests plus the bounded-concurrency test.
4. Run banking and payroll synthetic investigations with `--orchestrator langgraph`.
5. Run the same scenarios against legacy and compare evidence IDs, citations, scan-policy audits,
   unsupported claims, safety findings, terminal behavior, and persisted audit correlation.
6. Stop for any authorization mismatch, evidence loss, missing audit, unsupported claim, safety
   failure, or scan-policy gap.

## Rollback

Immediate rollback retains the deployed code and selects legacy before restart:

```powershell
az containerapp update --name ca-database-support-ai-dev `
  --resource-group rg-database-support-ai-dev `
  --set-env-vars `
    "LANGGRAPH_KILL_SWITCH=true" `
    "LANGGRAPH_ENABLED=false" `
    "INVESTIGATION_ORCHESTRATOR_MODE=LEGACY" `
    "LANGGRAPH_ROLLOUT_PERCENT=0" `
    "LANGGRAPH_SHADOW_PERCENT=0"
```

Verify `/health`, `/ready`, and one legacy synthetic investigation after rollback. Do not remove
the legacy orchestrator or delete comparison, evidence, report, or audit records.
