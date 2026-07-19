# Evaluation cleanup dry-run inventory

Generated: 2026-07-19T16:59:15Z  
Mode: **dry-run only — no cleanup rows or files deleted**

## Correct protected final benchmark

| Field | Value |
|---|---|
| Protected logical run ID | `9fb0a20c-cf44-5a13-b194-c1d8641e559c` |
| Frozen run name | `benchmark-125-d5815fd-20260718T155134Z` |
| Repository commit | `d5815fd509a13cb9dd3eec28c859c79f205d3c80` |
| Annotated tag / target | `rc-v1.0-final` / exact same commit |
| Manifest SHA-256 | `45CAC02D759FAC6B67C5B738A26B5BD23E4C3294EB3E4CC10000D4FC029B3F45` |
| Requested / terminal / incomplete | 125 / 125 / 0 |
| Cleanup | 125/125 passed |
| Domain coverage | Banking 25, Clinic 25, Orders 25, Payroll 25, Shipping 25 |
| Application outcomes | 51 AI answered; 55 provider failures; 19 evidence insufficient |
| Deterministic results | 51 eligible: 48 pass, 3 fail |
| Judge results | 51 eligible: 49 completed, 2 failed; average 80.308 |
| Frozen artifacts registered | Release report, results CSV, summary, provenance, checksums |
| Proposal | **KEEP and hard-protect from deletion** |

The frozen package was selected from commit, tag target, manifest, checksums, execution lifecycle, cleanup, scenario coverage, published summary, and persisted source records—not from its name. All checksums passed. Every frozen CSV row mapped one-to-one to an original persisted execution before import.

The original benchmark history remains unchanged. A new logical run was added transactionally by copying the 125 selected execution records and their 51 deterministic, 51 Judge, and 51 review records. The 125 original one-scenario run records and frozen source files were not modified or deleted.

The previously proposed run `3772275f-f219-4999-9c31-28f8dd5dc411` is **not** the final release benchmark: it predates `d5815fd`, records a different commit, has 125 deterministic failures, and has three failed Judge records. It is now proposed for deletion with the other obsolete runs after explicit approval.

## Revised cleanup proposal

- Evaluation runs inventoried: **502**
- Proposed KEEP: **1**
- Proposed DELETE after explicit approval: **501**
- Exact per-run inventory: `run-inventory.csv`
- No cleanup has been executed.

## Database counts after additive import, before cleanup

| Table | Current | Protected final run | Proposed deletion | Projected after cleanup |
|---|---:|---:|---:|---:|
| `evaluation_runs` | 502 | 1 | 501 | 1 |
| `evaluation_scenario_executions` | 919 | 125 | 794 | 125 |
| `evaluation_deterministic_scores` | 493 | 51 | 442 | 51 |
| `evaluation_ai_judge_scores` | 436 | 51 | 385 | 51 |
| `evaluation_human_review_flags` | 436 | 51 | 385 | 51 |
| `evaluation_artifacts` | 5 | 5 | 0 | 5 |
| `evaluation_jobs` | 0 | 0 | 0 | 0 |
| `evaluation_metrics` | 0 | 0 | 0 | 0 |

The legacy investigation-result family contains zero rows. Shared test-scenario definitions and frozen fixtures are not cleanup targets.

## Integrity findings

- Orphan executions without runs: 0
- Orphan deterministic scores without executions: 0
- Orphan Judge scores without executions or deterministic scores: 0
- Orphan human-review flags without deterministic scores: 0
- Orphan artifact rows without runs: 0
- Relevant child foreign keys use `ON DELETE CASCADE`.
- No application/business database or fixture state is in scope.

## Approval boundary

The protected final benchmark is now correctly retained. Cleanup remains blocked pending explicit approval. The future transactional cleanup must refuse to delete the protected run ID, reject active runs, audit every row/path, and use recoverable artifact quarantine. Evaluation UI work should use this protected record and serve reports through application endpoints without exposing filesystem paths.
