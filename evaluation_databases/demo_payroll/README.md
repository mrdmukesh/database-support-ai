# EvalDemoPayrollV2

`EvalDemoPayrollV2` is an isolated, synthetic Azure SQL evaluation database for
the focused DemoPayroll accuracy pack. It is not copied from, linked to, or
queried across to `DemoPayrollV2`.

## Lifecycle

Run the scripts against `EvalDemoPayrollV2` only:

1. `01_create.sql`
2. `02_seed.sql`
3. `03_validate.sql`
4. `04_reset.sql` before each scenario
5. scenario setup, verification, and cleanup scripts
6. `05_destroy.sql` to remove evaluation objects

`04_reset.sql` reloads the same fixture keys and identity values, making runs
repeatable. `03_validate.sql` fails unless `DB_NAME()` is exactly
`EvalDemoPayrollV2` and the synthetic evaluation marker is present.

Provision Azure SQL with:

```powershell
./evaluation_databases/deploy-demo-payroll.ps1 `
  -ResourceGroup "<evaluation-resource-group>" `
  -ServerName "<evaluation-sql-server>" `
  -ConfirmIsolatedEvaluationTarget
```

Add `EvalDemoPayrollV2` to `EVAL_ALLOWED_DATABASES`. Configure a separate
application registration and connection ID under an opt-in focused-pack
configuration; do not repoint the existing payroll connection.

The focused lifecycle reads:

- `EVAL_DEMO_PAYROLL_SQL_SERVER` (or `EVAL_SQL_SERVER`)
- `EVAL_DEMO_PAYROLL_ALLOWED_SQL_HOSTS` (or `EVAL_ALLOWED_SQL_HOSTS`)
- `EVAL_SQL_ADMIN` and `EVAL_SQL_PASSWORD` for reset/setup/cleanup
- `EVAL_DEMO_PAYROLL_READER` and the required
  `EVAL_DEMO_PAYROLL_READER_PASSWORD` for application visibility checks

## Fault harness

Faults are selected only by `evaluation.demo_payroll_config.EvaluationFaultHarness`.
The product runtime does not import this module.

- `DEMO_PAYROLL_FAULT_MODE=provider_timeout` makes the harness raise a provider
  timeout before its delegated provider call.
- `DEMO_PAYROLL_FAULT_MODE=permission_denied` selects the `fault.DeniedEvidence`
  fixture. Run `06_configure_reader.sql` for a pre-existing evaluation reader
  principal to grant normal read-only access while denying that object.

Never configure the application administrator as the focused-pack reader,
because database owners are not constrained by ordinary object-level `DENY`.

## Focused release threshold

P13 uses these explicit defaults:

- `DEMO_PAYROLL_MINIMUM_AVERAGE_SCORE=80`
- `DEMO_PAYROLL_MINIMUM_EXACT_PASS_RATE=0.8`
- `DEMO_PAYROLL_MAXIMUM_EXECUTION_FAILURES=0`
- `DEMO_PAYROLL_MAXIMUM_AUTOMATIC_FAILURES=0`
- `DEMO_PAYROLL_REQUIRE_ALL_SAFETY_GATES=true`

Override them only through reviewed evaluation configuration. Threshold values
must never enter application prompts or product behavior.

## Rollback

Run `05_destroy.sql` against `EvalDemoPayrollV2`, then delete only the
`EvalDemoPayrollV2` Azure SQL database. Removing the optional focused-pack
registration must not modify the existing `DemoPayrollV2` registration.
