# Controlled demo and research deployment guide

## Scope

Use this guide only for demo, research, development, or controlled test deployments. Human review
is mandatory. Do not deploy this release as autonomous production diagnosis.

## Prerequisites

- Python 3.11 or newer; the release container uses Python 3.12
- Node.js 22 for the React build
- Docker for container packaging, when used
- ODBC Driver 18 and `sqlcmd` for protected SQL Server evaluation
- PostgreSQL 16 for the hosted application database, or a supported controlled MySQL database
- Alembic revision `0021`
- Read-only identities for investigated databases

Install with `pip install -e ".[api,dev]"`; install frontend dependencies with `npm ci` in
`frontend-react`.

## Environment variables

Configure values through an approved secret store. Never place values in source control or build
logs. Relevant names include:

- `APP_ENV`, `DATABASE_URL`, `JWT_SECRET`
- `STORAGE_BACKEND`, `LOCAL_STORAGE_ROOT`, `AZURE_STORAGE_CONNECTION_STRING`,
  `AZURE_STORAGE_CONTAINER`
- `AI_REASONING_ENABLED`, `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_MODEL`,
  `LLM_REASONING_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_REASONING_EFFORT`, `OPENAI_API_KEY`,
  `OPENAI_BASE_URL`
- `LANGGRAPH_ENABLED`, `INVESTIGATION_ORCHESTRATOR_MODE`, `LANGGRAPH_KILL_SWITCH`,
  `LANGGRAPH_ROLLOUT_PERCENT`, `LANGGRAPH_SHADOW_PERCENT`,
  `LANGGRAPH_SHADOW_LLM_ENABLED`
- `EVALUATION_WORKER_ENABLED`, `EVALUATION_SERVICE_CLIENT_ID`,
  `EVALUATION_SERVICE_CLIENT_SECRET`, `EVALUATION_SERVICE_USER_ID`,
  `EVALUATION_SERVICE_ORGANIZATION_ID`, `EVALUATION_SERVICE_WORKSPACE_ID`
- `EVAL_RESULTS_DATABASE_URL`, `EVAL_API_BASE_URL`, `EVAL_ORGANIZATION_ID`,
  `EVAL_WORKSPACE_ID`, `EVAL_USER_ID`, and the domain-specific `EVAL_CONNECTION_ID_*` names

## Migration and startup

1. Confirm the target is controlled and backed up.
2. Run `python -m alembic upgrade head` against the application metadata database.
3. Confirm `python -m alembic current` and `python -m alembic heads` both report `0021`.
4. Start the API with `python -m uvicorn legacydb_copilot.main:app --host 0.0.0.0 --port 8000`.
5. If an external evaluation worker is required, start
   `python -m evaluation.worker --poll-seconds 2`. Use one embedded worker or the approved external
   worker topology, not duplicate unmanaged workers.

## Health and smoke checks

- Verify `GET /health` returns a healthy response.
- Confirm effective runtime diagnostics show the expected commit, database engine, orchestration
  mode, scan controls, and worker state without displaying secrets.
- Confirm database connectivity and workspace isolation using read-only checks.
- Run `python -m evaluation.cli preflight` in the imported controlled evaluation environment.
- Run one approved pilot smoke scenario, not the protected 25-scenario suite, and verify completed
  persistence, evidence, citations, report artifacts, zero unsupported claims, and zero safety
  failures.

Controlled demo questions should use synthetic records and ask an analyst to investigate a known
failed transition, summarize verified status history, or explain a missing related record. Do not
include protected expected answers in prompts.

## Shutdown and rollback

Stop the evaluation worker, then stop the API gracefully. Preserve reports and audit records. For
an immediate orchestration rollback, enable `LANGGRAPH_KILL_SWITCH`, disable LangGraph and rollout,
select `LEGACY`, restart, and run the approved smoke check. If necessary, revert the release merge
or redeploy the recorded pre-merge image. Do not delete evidence or manually rewrite migrations.
