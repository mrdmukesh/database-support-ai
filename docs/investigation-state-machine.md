# Deterministic Investigation State Machine

The state ledger is enabled with `FEATURE_AGENTIC_INVESTIGATION_ENABLED=true`.
The default is `false`, preserving the existing non-agentic investigation path.

```mermaid
stateDiagram-v2
    [*] --> INITIALIZATION
    INITIALIZATION --> EVIDENCE_ASSESSMENT
    EVIDENCE_ASSESSMENT --> GAP_IDENTIFICATION
    GAP_IDENTIFICATION --> ACTION_SELECTION
    ACTION_SELECTION --> PLANNING
    PLANNING --> VALIDATION
    VALIDATION --> EXECUTION
    EXECUTION --> VERIFICATION
    VERIFICATION --> STATE_UPDATE
    STATE_UPDATE --> STOP_EVALUATION
    STOP_EVALUATION --> EVIDENCE_ASSESSMENT: next iteration
    STOP_EVALUATION --> ROOT_CAUSE_CONFIRMED
    STOP_EVALUATION --> ISSUE_NOT_REPRODUCED
    STOP_EVALUATION --> INSUFFICIENT_EVIDENCE
    STOP_EVALUATION --> BLOCKED_BY_MISSING_SOURCE
    STOP_EVALUATION --> QUERY_BUDGET_EXHAUSTED
    STOP_EVALUATION --> ITERATION_BUDGET_EXHAUSTED
    STOP_EVALUATION --> POLICY_BLOCKED
    state terminal <<choice>>
```

Every transient state also supports `FAILED` and `CANCELLED`. Policy and budget
terminal states are reachable at their relevant decision boundaries. Terminal
states reject every subsequent transition.

Each persisted transition records investigation, organization and workspace
scope, previous/current state, UTC timestamp, reason, and iteration number.

Read-only API:

- `GET /investigations/{investigation_id}/state`
- `GET /investigations/{investigation_id}/state/history`
