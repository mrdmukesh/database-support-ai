# Benchmark Testing Framework

This folder contains demo-only benchmark assets for validating Database Support AI behavior.

The benchmark databases intentionally contain seeded production-style issues:

- normal business data
- duplicate child records
- missing child records
- retry failures
- batch failures
- slow query scenarios
- deadlock risk procedures
- missing-index scenarios

Ground truth is stored in `ai_expected_issues`.

The benchmark runner:

1. Reads benchmark questions from `ai_expected_issues`.
2. Runs the deterministic investigation engine.
3. Generates and runs safe verification checks.
4. Compares affected object, procedure, evidence, and root-cause wording to ground truth.
5. Produces accuracy metrics.

Safety rule: do not install these tables in customer databases.

The runner refuses to execute unless the database name contains one of:

- `demo`
- `test`
- `benchmark`
- `sample`
- `sandbox`

Example:

```powershell
python -m legacydb_copilot.benchmark_cli `
  --engine mysql `
  --connection-string "mysql://appadmin:password@host:3306/clinic_ops_ai_demo?ssl=true"
```

SQL fixtures:

- `demo_mysql/01_schema.sql`
- `demo_mysql/02_procedures.sql`
- `demo_mysql/03_seed.sql`
