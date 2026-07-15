# Automated evaluation runner — Phase 1

The release benchmark contains 125 scenarios. See [BENCHMARK.md](BENCHMARK.md) for named
suites, distribution, validation, reporting, and the complete safe scenario inventory.

The runner submits scenario questions through `POST /chat/ask`, polls the saved result through
`GET /learning/investigations/{id}`, and then reads the already-persisted investigation snapshots
for fields not exposed by the public detail response. It never calls reasoning, LLM, RAG, evidence,
or report-generation functions directly.

Required environment variables:

- `DATABASE_URL`: application/evaluation persistence database
- `EVAL_API_BASE_URL` and either `EVAL_SERVICE_CLIENT_ID` plus `EVAL_SERVICE_CLIENT_SECRET`
  (recommended), or `EVAL_ACCESS_TOKEN` for short interactive runs
- `EVAL_ORGANIZATION_ID`, `EVAL_WORKSPACE_ID`, `EVAL_USER_ID`
- `EVAL_CONNECTION_ID_PAYROLL`, `EVAL_CONNECTION_ID_CLINIC`, `EVAL_CONNECTION_ID_ORDERS`
- `EVAL_CONNECTION_ID_BANKING`, `EVAL_CONNECTION_ID_SHIPPING`
- `EVAL_SQL_SERVER`, `EVAL_SQL_ADMIN`, `EVAL_SQL_PASSWORD`

For unattended jobs, configure matching API/container secrets:
`EVALUATION_SERVICE_CLIENT_ID`, `EVALUATION_SERVICE_CLIENT_SECRET`,
`EVALUATION_SERVICE_USER_ID`, `EVALUATION_SERVICE_ORGANIZATION_ID`, and
`EVALUATION_SERVICE_WORKSPACE_ID`. The user must have active membership in the workspace.
Tokens default to 15 minutes (`EVALUATION_SERVICE_TOKEN_MINUTES`) and renew automatically
after an HTTP 401. Never commit service secrets or bearer tokens.

Examples:

```powershell
python -m evaluation.cli run-scenario --scenario-id shipping-pilot-001
python -m evaluation.cli run-domain --domain shipping
python -m evaluation.cli run-category --category root_cause
python -m evaluation.cli run-difficulty --difficulty hard
python -m evaluation.cli run-all --run-name pilot-v1 --concurrency 1
python -m evaluation.cli resume --run-id <run-id>
python -m evaluation.cli rerun-failed --run-id <run-id>
python -m evaluation.cli status --run-id <run-id>
python -m evaluation.cli validate-run --run-id <run-id>
python -m evaluation.cli judge-run --run-id <run-id>
python -m evaluation.cli judge-result --result-id <result-id>
python -m evaluation.cli list-human-review --run-id <run-id>
```

Concurrency defaults to one. Higher concurrency can process different domains concurrently, while
a process-wide domain lock prevents overlapping defect scenarios against the same database.

## AI judge configuration

The secondary judge requires `OPENAI_API_KEY`. Optional settings are:

- `EVAL_JUDGE_MODEL` and `EVAL_SECOND_JUDGE_MODEL`
- `EVAL_JUDGE_TIMEOUT_SECONDS` and `EVAL_JUDGE_MAX_RETRIES`
- `EVAL_JUDGE_RETRY_BACKOFF_SECONDS`
- `EVAL_HUMAN_REVIEW_SAMPLE_RATE` and `EVAL_HUMAN_REVIEW_SAMPLE_SEED`
- `EVAL_JUDGE_INPUT_COST_PER_MILLION` and `EVAL_JUDGE_OUTPUT_COST_PER_MILLION`

Judge temperature is fixed at zero. Application confidence is removed from the primary judge payload
and is used only by the local human-review policy after semantic scoring.
# Pilot execution readiness

Copy `.env.evaluation.example` to `.env.evaluation`, replace every placeholder, and load it into
the current PowerShell process. `.env.evaluation` is ignored by Git. Runner SQL credentials are
destructive and restricted to the five marked synthetic databases; application connection IDs
must use separate read-only credentials.

Execution order (PowerShell, from the repository root):

```powershell
./evaluation_databases/deploy-local.ps1 -Server $env:EVAL_SQL_SERVER -AdminUser $env:EVAL_SQL_ADMIN -Password (Read-Host -AsSecureString "Evaluation SQL password")
$env:EVAL_LIVE_SQL_TESTS="1"; pytest -q tests/test_evaluation_databases.py
alembic upgrade head
uvicorn legacydb_copilot.main:app --host 127.0.0.1 --port 8000
python -m evaluation.cli preflight
python -m evaluation.cli run-scenario --scenario-id shipping-pilot-001 --dry-run
python -m evaluation.cli pilot-smoke --run-name pilot-smoke-v1
python -m evaluation.cli run-all --run-name pilot-v1
python -m evaluation.cli validate-run --run-id <run-id>
python -m evaluation.cli judge-run --run-id <run-id>
python -m evaluation.cli list-human-review --run-id <run-id>
```

Azure deployment (placeholders only; Microsoft Entra authentication):

```powershell
./evaluation_databases/deploy-azure.ps1 -ResourceGroup "<resource-group>" -ServerName "<evaluation-sql-server>" -Location "<azure-region>"
```

`run-all` is blocked until live preflight succeeds and the latest five-domain smoke report records
five completed cases, successful cleanup, and only the configured connection IDs. Smoke reports are
written beneath `EVAL_ARTIFACT_ROOT`.

## Read-only evaluation dashboard

Organization and super administrators can open the dashboard after starting the API and React UI:

```powershell
alembic upgrade head
uvicorn legacydb_copilot.main:app --host 127.0.0.1 --port 8001
Set-Location frontend-react
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Dashboard URL: `http://127.0.0.1:5173/app/evaluation`

The dashboard reads persisted runner, deterministic validator, AI judge, human-review, timing,
token, and cost records. It has no mutation endpoints. When no accessible run has persisted
executions, it renders an empty state and no score figures.
