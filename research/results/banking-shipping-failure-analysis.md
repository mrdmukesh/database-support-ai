# Banking and Shipping benchmark failure analysis

## Baseline and scope

- Baseline commit: `d5815fd509a13cb9dd3eec28c859c79f205d3c80`
- Verified annotated release tag: `rc-v1.0-final`
- Analysis branch: `feature/fix-banking-shipping-benchmark-failures`
- Official artifact set: `benchmark-125-d5815fd-20260718T155134Z`
- Analyzed failures: 25 Banking and 25 Shipping. No official result folder was changed or deleted.

The exact 50-row scenario inventory and stage-by-stage outcome is in `banking-shipping-before-after.csv`.

## Exact failure groups

| Domain | Failure category | Count | Scenario IDs |
|---|---:|---:|---|
| Banking | `PROVIDER_OTHER_FAILURE` | 21 | banking-pilot-001, -002, -003, -005; banking-benchmark-001, -002, -004, -005, -006, -008, -009, -010, -011, -012, -014, -015, -016, -017, -018, -019, -020 |
| Banking | `EVIDENCE_INSUFFICIENT` | 4 | banking-pilot-004; banking-benchmark-003, -007, -013 |
| Shipping | `PROVIDER_OTHER_FAILURE` | 22 | shipping-pilot-001 through -005; shipping-benchmark-001, -002, -004, -005, -006, -008, -009, -010, -011, -012, -014, -015, -016, -017, -018, -019, -020 |
| Shipping | `EVIDENCE_INSUFFICIENT` | 3 | shipping-benchmark-003, -007, -013 |

## Provider failures (43)

All 43 external failures occurred in the application-model call. The Judge was not eligible and never completed. The official trace preserved `HTTPError`, one attempt, zero retries, and the total scenario runtime, but did not preserve the HTTP status or per-request duration. Therefore these failures cannot be called rate limiting or proven temporary. Most had an exact resolved entity, executed SQL, collected evidence, and an accepted evidence gate before the application model failed. Those partial deterministic results remain in the official artifacts and the failed scenarios are safe to resume because every attempt resets before injection and always cleans up.

The provider client now retries only connection/timeouts, HTTP 429, and HTTP 5xx, with bounded exponential backoff, jitter, a total-duration bound, and circuit breaking. Authentication and other deterministic 4xx failures and malformed successful responses are not retried. Prospective traces retain HTTP status, exception type, attempt duration, attempts, and retries. Judge retries remain independent in the evaluation Judge service; no Judge failure was observed in this subset.

## Application and fixture findings

### Ambiguous identifiers: benchmark-003

`BNK-2026-0003` and `SHP-2026-0003` each match multiple canonical suffixed rows. The application correctly returned an ambiguity requiring user selection and did not run unsafe SQL. The expected answer also calls for stopping on multiple plausible records. No fuzzy resolution change was made. The frozen evaluator's AI-required classification turns this correct safe stop into `EVIDENCE_INSUFFICIENT`; this is an evaluator/expectation issue.

### Status contradictions: pilot-004 and benchmark-007

- banking-pilot-004 said batch `BAT-3104` remained `Running`, while injection created `Exception`. Injection and verification now consistently require `Running`.
- banking-benchmark-007 and shipping-benchmark-007 said the entity remained `Processing`, while injection created `Failed`. Injection and verification now consistently require `Processing`.

Changing the question or expected answer was rejected because the linked exception evidence and scenario intent support the reported status. These corrections make the fixture executable against its existing natural-language contract, but the next run must be identified as using corrected fixtures when compared with the official run.

### Relationship discovery: banking-pilot-004

The batch and exception rows share the exact `CorrelationId`, but the synthetic schema has no FK. The gate previously accepted only joins or metadata FKs. It now recognizes the same non-empty correlation key/value across two distinct SQL tables. Repetition inside one table cannot invent a relationship.

### Target selection: benchmark-013

Generic nouns such as “payment” or “shipment” could outweigh the table whose bounded entity-proof query returned the exact identifier. Target selection now prefers that unique database-proven table, including a uniquely resolvable schema leaf, and fails closed if provenance spans candidates.

Banking benchmark-013 still has an apparent procedure mismatch: its beneficiary fixture expects `eval.usp_banking_workflow_5`, while that procedure updates loans; workflow 3 targets beneficiaries. Shipping benchmark-013 expects workflow 5 for `shipment_milestones`, while workflow 5 updates voyages and none of workflows 1–8 targets shipment milestones. These were not changed because a conclusive intended correction cannot be selected without benchmark-owner input.

## Evidence planning

The existing orchestration already performs a bounded correlation follow-up after primary evidence. The observed pilot-004 failure was interpretation of already-collected correlation evidence, not absence of a planned query. The benchmark-003 cases correctly stop before SQL when resolution is ambiguous. No unbounded or speculative planner expansion was introduced.

## Current validation state

The read-only preflight passed both Banking and Shipping database markers and target allowlisting, but failed because the investigation worker was stopped and the application API was unreachable. Consequently no failed scenario was rerun and no “now passing” claim is made. The CSV uses `NOT_RERUN_PREFLIGHT_BLOCKED`, not a synthetic pass/fail result.
