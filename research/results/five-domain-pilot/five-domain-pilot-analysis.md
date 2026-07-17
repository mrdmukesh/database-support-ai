# Five-Domain Native SQL Server Pilot — Hard-Stop Report

## Outcome

The controlled pilot hard-stopped on Banking, as required. Shipping reused the already validated successful result. Orders, Payroll, and Clinic were not executed. No 25- or 125-scenario suite was started.

- Pilot status: **HARD_STOPPED**
- Passing results: **1 of 5 requested** (Shipping)
- Newly executed scenarios: **1** (Banking)
- Scored-result deterministic average: **93.055**
- Scored-result AI Judge average: **92.15**
- Scored-result human-review rate: **0%**
- Safe to begin 25 scenarios: **No**

The averages describe Shipping only and must not be interpreted as five-domain pilot averages.

## Hard-stop diagnosis

`banking-pilot-001` expects the business entity `TRF-3101`. Its injection script creates an exception mentioning that identifier and changes `eval.transactions` row 1, whose business key remains `BANKING-004`. The seed contains `MSG-TRF-3101` and `CORR-TRF-3101`, but no exact `TRF-3101` business key in `eval.transfers` or another resolver-supported business-key column.

The setup verification script checks the exception and modified transaction, then prints `TRF-3101`; it does not verify that the expected entity itself exists. Consequently:

1. SQL setup verification returned `verified=true`.
2. Exact entity resolution correctly returned `not_found`.
3. Canonical fallback `TRF-3101` was persisted from the user question, but no database-resolved/evidence-linked entity existed.
4. Evidence collection and the evidence gate were not reached.
5. Application AI was correctly not invoked because no safe database entity was resolved.
6. The benchmark runner correctly marked the execution `invalid_configuration` because an AI-enabled pilot requires a recorded AI invocation.
7. Cleanup passed.

This is classified as **MISSING_TEST_DATA / FIXTURE_CONTRACT_MISMATCH**, not an application accuracy failure and not an entity-serialization leak.

## Framework assessment

A shared **benchmark fixture-generation and verification defect** is confirmed. Read-only inspection shows the same pattern in all three unrun domain contracts:

- Orders expects `ORD-7101`, but seeds only `MSG-ORD-7101`/`CORR-ORD-7101` and mutates a generic inventory row.
- Payroll expects `EMP-1042`, but seeds only `MSG-EMP-1042`/`CORR-EMP-1042` and mutates a generic pay-group row.
- Clinic expects `APT-2101`, but seeds only `MSG-APT-2101`/`CORR-APT-2101` and mutates a generic appointment row.

Their verification scripts prove the exception and generic row mutation, then print the expected entity without proving an exact entity row exists. These contracts were not executed after the Banking hard stop. The application resolver, canonical serializer, AI invocation guard, and hard-stop behavior worked as designed.

## Results

| Domain | Scenario | Database | Fixture | Canonical entity | Evidence gate | AI invoked | Provenance | Deterministic | Judge | Human review | Runtime | Tokens | Failure stage | Classification |
|---|---|---|---|---|---|---|---|---:|---:|---|---:|---:|---|---|
| Banking | banking-pilot-001 | EvalBanking | INVALID semantic fixture | TRF-3101 | Not reached | No | INSUFFICIENT_DATABASE_EVIDENCE | — | — | N/A | 9.194s | 0 | entity_resolution | Missing test data / fixture-contract mismatch |
| Orders | orders-pilot-001 | EvalOrders | Not run | — | Not run | — | NOT_RUN | — | — | N/A | — | — | not_started | Banking hard stop |
| Shipping | shipping-pilot-001 | EvalShipping | VALID | SHP-5001 | Accepted | Yes | AI_ANSWERED | 93.055 | 92.15 | No | 27.576s | 5,890 | — | PASS |
| Payroll | payroll-pilot-001 | EvalPayroll | Not run | — | Not run | — | NOT_RUN | — | — | N/A | — | — | not_started | Banking hard stop |
| Clinic | clinic-pilot-001 | EvalClinic | Not run | — | Not run | — | NOT_RUN | — | — | N/A | — | — | not_started | Banking hard stop |

## Gate decision

The 25-scenario validation is **not safe to begin**. The five-domain criteria were not met because only Shipping passed, and four domain pilot contracts share a missing-entity fixture defect. Repair must be generic at the fixture-contract/verification level; no domain-specific application hardcoding is recommended.
