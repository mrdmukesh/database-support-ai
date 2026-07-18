# FIX-EP-01 Verification Report

## Decision

Case B was proven for `shipping-benchmark-005`: required correlated evidence existed in the active database schema but `audit_history` and `exceptions` were omitted from the evidence-planning scope. A minimal generic production correction and an unseen-schema regression test were therefore required. No evidence-gate behavior was weakened.

The other three retry scenarios continued through evidence planning and AI reasoning. The two condition-proof scenarios remained correctly rejected by the evidence gate because their questions assert `Processing` while the verified fixture rows are `Failed`.

## Provenance

- Repository base commit: `7983961ef547c86b181eea7f877f6be8ac82f051`
- Benchmark runner commit: `7983961ef547c86b181eea7f877f6be8ac82f051`
- Isolated worktree: `D:\AI_Code\LegacyDB-Support-Copilot-FIX-EP-01`
- API base URL: `http://127.0.0.1:8011` (runner used equivalent `http://localhost:8011`)
- API process ID/start: `8812`, `2026-07-18T00:09:22.047664+00:00`
- Worker process ID/start: `9520`, `2026-07-18T00:09:23.337061+00:00`
- API and worker `application_commit`: `7983961ef547c86b181eea7f877f6be8ac82f051`
- Imported production module: `D:\AI_Code\LegacyDB-Support-Copilot-FIX-EP-01\src\legacydb_copilot\routers\chat.py`
- Provider/model: OpenAI / `gpt-4.1-mini`; AI, LLM, verification agent, metadata discovery, safe SQL, collection, and verification all enabled.

Port 8000 was proven to host the stale `7fb451c1...` process. Attempts that reached that process were rejected before investigation and were discarded. The conclusive runs used dedicated port 8011. A stale static token and mismatched tenant variables were also discarded; conclusive runs used a fresh service token and the token owner's existing Research Benchmark workspace and five connections.

## Root cause

`_run_dynamic_investigation` ranked relevant tables, then attempted to append diagnostic tables from `context.metadata.tables`. That metadata object was already relevance-truncated. For shipping, it retained `integration_messages` but excluded active `audit_history` and `exceptions`, so correlation expansion could not generate SQL for them even though fixture audit proved the rows existed.

The generic correction adds `_metadata_with_active_diagnostics` in `src/legacydb_copilot/routers/chat.py:1686` and calls it at line 1834. It retains the first eight ranked tables and fills the remaining bounded scope (maximum 12) with diagnostic tables from complete active-schema `resolution_metadata`. It contains no domain, table, scenario, entity, expected-answer, or benchmark-ID special case.

## Before/after evidence

- Before: shipping generated 11 statements and retrieved milestone/integration evidence, but generated no `audit_history` or `exceptions` SQL. Deterministic validation failed despite an unadjusted score of 77.072; Judge invocation failed its response-schema validation.
- After: shipping discovered `eval.audit_history` and `eval.exceptions`, generated 13 statements including correlation queries against both for `EVAL-SHIPPING-105`, passed the evidence gate, invoked AI, and passed deterministic validation at 83.945. Judge completed at 83.95.
- Banking, orders retry, and payroll retry all passed at 80.373; each Judge completed at 80.35.
- Orders 007 and clinic 007 retrieved their correlated diagnostic evidence but stopped before AI. This is expected: verified primary status is `Failed`, so the reported `Processing` condition is not proven. They are benchmark/fixture-question contradictions, not planner failures.

## Scenario results

| Scenario | Entity / primary | SQL and rows | Gate / AI / Judge | Final |
|---|---|---|---|---|
| banking-benchmark-010 | BNK-2026-0010-A / transfers | Exact, identifier and correlation SQL plus audit/exception/message evidence; correlated rows returned | pass / yes / yes | pass 80.373 |
| orders-benchmark-010 | ORD-2026-0010-A / sales_order_lines | Exact, identifier and correlation SQL plus audit/exception/message evidence; correlated rows returned | pass / yes / yes | pass 80.373 |
| shipping-benchmark-005 | SHP-2026-0005-A / integration_messages; resolved in shipment_milestones | 13 statements; milestone, integration, audit and exception correlation rows returned | pass / yes / yes | pass 83.945 |
| payroll-benchmark-010 | PAY-2026-0010-A / payroll_items | Exact, identifier and correlation SQL plus audit/exception/message evidence; correlated rows returned | pass / yes / yes | pass 80.373 |
| orders-benchmark-007 | ORD-2026-0007-A / receipts | Entity and correlated diagnostic evidence returned; primary status `Failed` | condition unproven / no / no | invalid_configuration (expected gate rejection) |
| clinic-benchmark-007 | CLN-2026-0007-A / payments | Entity and correlated diagnostic evidence returned; primary status `Failed` | condition unproven / no / no | invalid_configuration (expected gate rejection) |

The compact machine-readable outcome is in `fix-ep-01-targeted-results.csv`; representative generated SQL and the correlated evidence result are recorded above.

## Tests

- Red proof: importing `_metadata_with_active_diagnostics` before implementation failed because it did not exist.
- `test_evidence_scope_retains_unseen_active_schema_diagnostics`: passed. Uses unseen `ops.*` identifiers and proves active diagnostic tables survive a relevance-truncated ranked set.
- `test_related_evidence_expands_string_correlation_ids`: passed.
- `test_production_retry_condition_does_not_require_duplicate_evidence`: passed.
- Live targeted rerun: 6/6 executed conclusively; 4 eligible results validated and judged, 2 gate-ineligible results remained blocked for the proven condition mismatch.

An earlier five-test command executed test bodies but stalled during the environment's suite teardown and was terminated; it is not counted as conclusive. The three focused tests above exited normally.

## Scope and risks

Production runtime behavior changed only in evidence-scope construction: unseen active diagnostic objects can now be considered for safe, correlation-based evidence planning within the existing 12-table cap. Validation, evidence-gate rules, SQL safety, Judge logic, fixtures, scenarios, and expected answers were unchanged.

Remaining issue: `orders-benchmark-007` and `clinic-benchmark-007` ask about `Processing`, but their verified fixtures contain `Failed`. Their `invalid_configuration` label is mechanically correct under current runner rules, though a more descriptive condition-mismatch classification/report would improve reporting. This report does not propose weakening the gate.

Recommendation: accept FIX-EP-01. Correct the two fixture/question contradictions before treating those scenarios as application-accuracy measurements.
