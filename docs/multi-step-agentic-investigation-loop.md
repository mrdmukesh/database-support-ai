# Multi-Step Agentic Investigation Loop (AG-05)

AG-05 orchestrates the existing deterministic investigation components one evidence request
at a time. It is enabled only by `FEATURE_AGENTIC_INVESTIGATION_ENABLED`; the existing
single-pass investigation remains the default.

## Iteration flow

```text
EVIDENCE_ASSESSMENT
  -> GAP_IDENTIFICATION
  -> ACTION_SELECTION (logical EvidenceRequest only)
  -> PLANNING (existing deterministic SQL planner)
  -> VALIDATION (existing read-only SQL validator)
  -> EXECUTION (approved read-only SQL only)
  -> VERIFICATION
  -> STATE_UPDATE (persist step, evidence, and budgets)
  -> STOP_EVALUATION
       |-> terminal state
       `-> EVIDENCE_ASSESSMENT (next controlled iteration)
```

The loop does not call an LLM to generate or execute SQL. A logical request is adapted to
the existing provider-specific planner, and every generated statement is passed through
`validate_read_only_sql` and the existing execution safety validators. A failed or blocked
query remains execution-failure evidence and is never converted to verified absence.

## Limits

| Environment variable | Default |
|---|---:|
| `AGENTIC_MAX_ITERATIONS` | 8 |
| `AGENTIC_MAX_SQL_QUERIES` | 16 |
| `AGENTIC_MAX_TOTAL_ROWS` | 1000 |
| `AGENTIC_MAX_EXECUTION_SECONDS` | 120 |
| `AGENTIC_MAX_LLM_CALLS` | 8 |
| `AGENTIC_MAX_TOKENS` | 32000 |
| `AGENTIC_MAX_RETRIES` | 1 |

Limits are cumulative for the investigation loop. Query/row exhaustion terminates safely as
`QUERY_BUDGET_EXHAUSTED`; iteration, duration, LLM-call, and token exhaustion terminate as
`ITERATION_BUDGET_EXHAUSTED`. An unknown root cause is not an internal failure: when no
eligible evidence action remains, the terminal state is `INSUFFICIENT_EVIDENCE`.

## Persistence and timeline API

Migration `0016_agentic_loop` creates `investigation_agentic_steps`. Each row contains:

- iteration and state;
- logical request and stable action fingerprint;
- deterministic planned queries;
- newly verified evidence;
- gap snapshot;
- cumulative budgets;
- outcome, reason, and duration.

The ordered timeline is available from:

```text
GET /investigations/{investigation_id}/agentic-steps
```

## Example step timeline

```json
[
  {
    "iteration_number": 1,
    "state": "STATE_UPDATE",
    "evidence_request": {
      "request_type": "ENTITY_LOOKUP",
      "entity_scope": "EXACT_KEY",
      "entity_type": "PayrollItem",
      "entity_key": "PI-404"
    },
    "outcome": "SUCCEEDED",
    "budget": {"iterations": 1, "sql_queries": 1, "total_rows": 1}
  },
  {
    "iteration_number": 2,
    "state": "STATE_UPDATE",
    "evidence_request": {
      "request_type": "WORKFLOW_TRACE",
      "entity_scope": "EXACT_KEY",
      "entity_type": "PayrollItem",
      "entity_key": "PI-404"
    },
    "outcome": "SUCCEEDED",
    "budget": {"iterations": 2, "sql_queries": 2, "total_rows": 3}
  }
]
```

## DemoPayrollV2 live validation

The validation harness executes the local AG-05 implementation while routing generated SQL
through the existing validators and an Azure Container App connector. It performs bounded,
read-only queries and does not deploy code or change database data.

```powershell
.\.venv\Scripts\python.exe scripts/validation/run_agentic_payroll_live.py `
  --app-name <container-app> `
  --resource-group <resource-group> `
  --revision <active-revision> `
  --connection-id <DemoPayrollV2-connection-id> `
  --employee-key EMP-1001
```

Validated timeline:

| Iteration | Logical request | Result | Rows | Cumulative SQL |
|---:|---|---|---:|---:|
| 1 | `ENTITY_LOOKUP` | succeeded | 1 | 1 |
| 2 | `RELATED_RECORDS` | succeeded, verified absence | 0 | 2 |

Terminal state: `INSUFFICIENT_EVIDENCE`.

Terminal reason: the PayrollItem absence is verified for the employee, but the available
database evidence does not establish why creation did not occur. This deliberately avoids
fabricating a root cause or treating an unknown cause as an internal failure.
