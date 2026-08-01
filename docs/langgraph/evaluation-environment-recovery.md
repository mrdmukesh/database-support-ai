# Evaluation environment recovery

## Configuration and permissions

Keep secrets in `.env.evaluation` or the approved secret store. Required non-secret identities
are the API URL, organization/workspace/user IDs, five connection IDs, SQL engine/server, exact
host allowlist, and `EvalPayroll`, `EvalClinic`, `EvalOrders`, `EvalBanking`, and `EvalShipping`.
Runner administration credentials and application read-only credentials must be separate.

The application identity needs `CONNECT`, `db_datareader`, and metadata visibility for
`sys.tables`, `sys.columns`, `sys.schemas`, `sys.procedures`, `sys.sql_modules`,
`sys.foreign_keys`, and `sys.indexes`. Deny `INSERT`, `UPDATE`, `DELETE`, and `EXECUTE`. Never use
the evaluation administrator in application connection records.

## Start and verify

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\evaluation\start-local-evaluation.ps1
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
python -m evaluation.cli preflight
python -m legacydb_copilot.services.llm_model_preflight
```

API and worker must report the same commit and migration. `/ready` must return HTTP 200.
Preflight tests every application connection, database identity, host/port allowlist, synthetic
marker, judge configuration, manifest, and ground-truth isolation.

## Read-only SQL diagnostics

```sql
SELECT @@SERVERNAME, DB_NAME(), ORIGINAL_LOGIN(), SUSER_SNAME(), USER_NAME();
SELECT COUNT(*) FROM sys.tables;
SELECT COUNT(*) FROM sys.columns;
SELECT COUNT(*) FROM sys.schemas;
SELECT COUNT(*) FROM sys.procedures;
SELECT COUNT(*) FROM sys.sql_modules;
SELECT COUNT(*) FROM sys.foreign_keys;
SELECT COUNT(*) FROM sys.indexes;
```

If the contained reader credential is unavailable, a DBA may review and run
`evaluation_databases/provision_readonly_user.py` with a newly generated
`EVAL_READER_PASSWORD`, then place five database-specific URLs in the approved secret store.
This performs DDL and credential rotation; Codex does not execute it automatically. Update the
five control records to the exact host/database and read-only secret references, then test each
`/databases/connections/{id}/test`.

## Target normalization

SQL Server targets normalize an optional `tcp:` prefix, host case, trailing dot, and default port
1433. Non-default ports must be explicitly allowlisted as `host:port`. Partial hostnames,
unlisted aliases, wrong ports, missing identity, production-like hosts, wrong databases, and
missing synthetic markers fail closed.

Local SQL Server on port 14333 uses:

```text
EVAL_SQL_SERVER=127.0.0.1,14333
EVAL_ALLOWED_SQL_HOSTS=127.0.0.1:14333,localhost:14333
```

## Smoke, benchmark, and recovery

Keep legacy/disabled/zero rollout for the first smoke. Run five-domain pilot smoke only after
preflight passes. Enable LangGraph only in evaluation after `/ready` proves registered
composition. Run deterministic and model-backed smoke, fallback/timeout/malformed-response
tests, and kill-switch validation before:

```powershell
python -m evaluation.cli run-all --run-name legacy-gpt-4.1-mini --orchestrator legacy
python -m evaluation.cli run-all --run-name langgraph-gpt-4.1-mini --orchestrator langgraph
python -m evaluation.cli run-all --run-name langgraph-gpt-5.1 --orchestrator langgraph
```

The runner rejects orchestration labels that do not match API runtime. Never change manifests,
expected results, scores, or target guards to clear a gate.

Common recovery:

- API unreachable: start it and inspect sanitized `api.err.log`.
- Worker unhealthy: verify PID, runtime readiness, control DB, migration, and commit.
- Connection timeout/login failure: verify firewall, host/database, and read-only secret.
- Target rejected: correct exact configuration; never add wildcards.
- LangGraph unavailable: retain legacy and register reviewed production facades.
- Migration mismatch: back up and migrate only the control database.

Remove temporary workstation firewall rules after validation. Preserve evidence, audits,
comparison artifacts, and the previous immutable image during rollback.
