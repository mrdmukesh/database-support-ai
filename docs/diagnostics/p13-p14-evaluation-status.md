# P13–P14 Evaluation Status

This checkpoint records the focused `EvalDemoPayrollV2` development and
evaluation baseline. It is not production release approval.

## Benchmark results

| Run | Exact passes | Average deterministic score | Execution failures | Automatic safety failures |
|---|---:|---:|---:|---:|
| P13 baseline (`5d91b2ae-95bd-4639-b490-32da8ed241db`) | 0/5 | 48.5 | 2 | 0 |
| P14 iteration 1 (`b2fe7116-79f2-4684-945a-41a2c450d5b0`) | 1/5 | 53.5 | 0 | 0 |

The release recommendation remains **DO_NOT_RELEASE**.

## Known limitations

- Factual evidence preservation, including verified NULL values, is incomplete.
- Report composition is incomplete for zero-row and insufficient-evidence paths.
- Multi-object payroll evidence planning does not consistently include all
  relevant payroll and procedure evidence.
- Employee and department findings can be incomplete.
- Finding extraction and terminal-state semantics require further refinement.

## Safety and scope

Both runs recorded zero automatic safety failures. No mutating SQL,
administrator database lifecycle operation, `fault.DeniedEvidence` access,
`DemoPayrollV2` targeting, or selection of another database was observed.

Merging this checkpoint is permitted only as a development and evaluation
baseline. It does not authorize production deployment; application deployment
remains blocked.
