# LG-08 release-readiness report

- Branch: `feature/langgraph-workflow-evidence`
- Starting commit: `ed0e7f44491a8512989b0d9b5fee90268e8ad0e4`
- Candidate commit: pending final commit after validation
- Default routing: legacy; LangGraph disabled; rollout/shadow zero
- LG-08 tests: 70 passed
- Complete backend: 1,637 passed, 5 existing skips
- Frontend: 209 passed; build and TypeScript passed; ESLint 0 errors/8 existing warnings
- Dependency check and changed-scope Ruff: passed
- Protected manifest validation: passed through existing benchmark validation suite
- Protected dry-run: passed for `shipping-pilot-001` with orchestrator `langgraph`
- Live protected benchmark: not yet executed
- Shadow comparison: not yet executed against supervised live infrastructure
- Safety gates: implementation tests pending final validation
- Migrations: none

Decision: `BLOCKED_BY_ENVIRONMENT`

The code may be eligible for deployment in Phase 0 after tests pass, but production activation is
not approved. Required evidence is a successful protected LangGraph benchmark, reviewed
legacy/candidate comparison artifacts, approved database-load and provider-cost tolerances,
registered production service facades, operational monitoring ownership, rollback exercise, and
change-management approval.

## LG-09 model release gate

- Previous/default development model: `gpt-4.1-mini`
- Candidate evaluation/staging model: `gpt-5.1`
- Explicit fallback: `gpt-4.1-mini`
- Cost-constrained supported candidate: `gpt-5-mini`
- API endpoint: configured `OPENAI_BASE_URL` plus `/responses`
- Candidate parameters: reasoning effort `medium`, maximum output tokens `4000`,
  provider timeout `60` seconds
- Production routing configuration: `LEGACY`; LangGraph disabled; rollout and shadow zero
- Model-access preflight command:
  `python -m legacydb_copilot.services.llm_model_preflight`
- Provider access: verified from the configured local evaluation account on 2026-07-30;
  `gpt-5.1` returned parseable structured output through `/responses` (18 input tokens,
  48 output tokens). Cost telemetry was captured as `0.0` because application reasoning
  price settings were not configured in that shell, so this is not benchmark cost evidence.
- Protected baseline/candidate benchmark: not yet run
- Model comparison, latency, token, and cost artifacts: not yet generated
- Selected production model: retain `gpt-4.1-mini` until all release gates pass
- Production activation: not performed
- Deployment: not performed; the protected evaluation preflight failed because the worker and
  application API were unavailable, application connections could not be inventoried, and the
  local SQL target/markers did not satisfy the non-production allowlist.
- Smoke investigation: not run because the application API health check failed.

LG-09 adds configuration and a fail-closed model-access guard. Setting a candidate model does
not mark it verified and does not activate LangGraph. A deployment operator must run the
sanitized preflight with the deployment account, review benchmark comparison artifacts, and set
`LLM_MODEL_ACCESS_VERIFIED=true` only for an approved environment after access and release
evidence have been verified. The successful local account probe does not verify a future
container deployment identity and does not clear the protected benchmark gate.

## LG-10 recovery and validation

Decision: `NOT_READY`

Captured 2026-07-31 on `feature/langgraph-workflow-evidence` from LG-09 commit
`48abe6afbf74207f5755c4601bd0fe35b4b2cc6f`.

- API: restored at `http://127.0.0.1:8000`; `/health` is `ok`; `/ready` is `ready` in
  legacy mode. The control database is reachable and migration `0021` matches repository head.
- Worker: restored and polling with the same commit/configuration and ready control dependencies.
- Azure SQL: the intended exact server and five `Eval*` databases are online. Read-only
  diagnostics verified identities and metadata catalogs using the evaluation administrator.
- Allowlist/markers: pass with exact process-only Azure host and five-database configuration.
  Wrong host, database, port, alias, and missing identity remain rejected by tests.
- Application connections: fail. Their records and secret URLs target the stopped local SQL
  instance. Both Azure contained reader users exist with read-only roles, but available
  credential sources do not authenticate. No reader password was reset and no DDL was executed.
- Model: `gpt-5.1` passed `/v1/responses` structured parsing with 18 input and 36 output tokens.
  Estimated cost was `0.0` because application-model pricing was not configured in the probe
  shell; this is not benchmark cost evidence.
- LangGraph composition: unavailable and disabled. Legacy is available, but real LangGraph smoke
  and benchmark execution cannot occur.
- Smoke investigations: not run because the five connection gates did not pass.
- Protected benchmark: not run because preflight failed. The runner now rejects a LangGraph label
  when the runtime is legacy or lacks registered composition.
- Comparisons: no baseline/candidate scores, latency, token, or cost results were fabricated.
- Candidate artifact/deployment/production activation: not performed. Local Docker was
  unavailable and release gates failed, so no candidate image was published or deployed.
- Validation: 87 focused LG-09/LG-10/LangGraph tests passed; full backend 1,661 passed
  with five existing protected-resource skips; `pip check` passed; frontend 209 passed;
  TypeScript and production build passed; ESLint reported zero errors and eight existing
  warnings; changed-scope Ruff passed. Repository-wide Ruff still has unrelated legacy findings.
- Rollback artifact: commit/image `47dad9433529c5232165e92b232c4eb68084a284`,
  digest `sha256:85a34cac69b6c696c0ad83f7f09c38b53ed886d123539f3f4bca402dcb171a8f`,
  revision `ca-database-support-ai-dev--0000154`.

Release remains blocked until a DBA supplies or rotates the least-privilege contained reader
credential, the five application secrets/records pass connectivity tests, and reviewed
production LangGraph facades are registered. Then repeat preflight, smoke, fallback/kill-switch,
and separate protected baseline/candidate benchmarks.
