# Banking and Shipping focused rerun aggregate

Date: 2026-07-19

## Application and deterministic results

| Domain | Run ID | Runner completed | Deterministic passes | Cleanup |
|---|---|---:|---:|---:|
| Banking | `ab127550-5507-4fef-9ee3-d50a540271cd` | 23/25 | 23/23 | 25/25 |
| Shipping | `6cba0fef-f02a-41b4-95a7-b35963f5e5b6` | 23/25 | 23/23 | 25/25 |

The 43 scenarios that previously failed during the application-model call all completed. The four non-completions are Banking and Shipping benchmark-003 (safe ambiguous identifier stop) and benchmark-013 (unresolved evidence-gate/procedure-fixture mismatch).

## Shipping Judge-only recovery

No Banking or Shipping application benchmark was rerun during Judge recovery. The following persisted Shipping result IDs were rescored with `evaluation.cli judge-result`:

| Scenario | Result ID | Latest Judge version | Status |
|---|---|---:|---|
| shipping-benchmark-019 | `e0b3e8af-8191-4d1a-b030-168bfef7e7f5` | 2 | completed |
| shipping-benchmark-020 | `f6fc3892-41f3-4d06-9caa-965562fd3513` | 2 | completed |
| shipping-pilot-001 | `a70f3166-1618-4b62-bc49-50d639036916` | 2 | completed |
| shipping-pilot-002 | `0852ac45-95d7-4f68-bdc4-6e78835b3d34` | 2 | completed |
| shipping-pilot-003 | `e7a414fa-8c8e-44e4-bda7-1f9b9ed8913c` | 2 | completed |
| shipping-pilot-004 | `6e3694c2-19eb-4af5-92b9-5c90daf670b4` | 2 | completed |
| shipping-pilot-005 | `b7f2b768-5423-4012-a402-04ddf18debab` | 2 | completed |

Latest-version aggregate query result: **23 completed / 23 eligible Shipping Judge evaluations**, average weighted score **84.156**. The earlier seven version-1 `HTTP 429 insufficient_quota` records remain append-only audit history and are superseded by successful version 2 results.
