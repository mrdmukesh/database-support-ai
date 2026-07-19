# Invalid Scenario Root-Cause Report

## Executive summary

Release candidate `7983961` produced 13 `invalid_configuration` results in the official 25-scenario validation run. The artifact-backed invalid list exactly matches the 13 scenarios in the investigation request.

All 13 are confirmed application-path defects. No benchmark, fixture, configuration, infrastructure, provider, judge, evidence-gate, or orchestration defect caused an invalid result.

Primary classifications are:

- 5 `APPLICATION_ENTITY_RESOLUTION_DEFECT`
- 4 `APPLICATION_TARGET_SELECTION_DEFECT`
- 4 `APPLICATION_EVIDENCE_PLANNING_DEFECT`

The strict evaluation classification is correct and must remain unchanged. AI-enabled scenarios without recorded invocation and positive token usage are unscoreable. The false-invalid aspect is upstream: validated evidence existed, but the application did not reach it.

## Validation-run details

- Benchmark folder: `research/results/official-validation-25-20260718`
- Total scenarios: 25
- Completed and scoreable: 12
- Passed: 6
- Scored failures: 6
- Invalid configuration: 13
- Infrastructure failures: 0
- Benchmark-run fixture audit: 125/125 valid
- Missing fixture entities: 0
- Missing defect evidence: 0
- Fixture verification failures: 0
- Cleanup: passed for every invalid scenario
- Invalid-scenario judge executions: 0, by design

All scenarios used organization `678264ff-8b4f-47a5-89dc-a90b9e371dde` and workspace `2f847a6a-9db2-4ae5-b144-71598ec8fb87`. Connection IDs are recorded in the JSON trace without credentials or connection strings.

## Methodology

The investigation reconciled:

- `benchmark-summary.json`
- `benchmark-progress.csv`
- `benchmark-results-detail.json`
- `benchmark-summary.md`
- `benchmark-console.log`
- all 13 invalid `*-run.log` files
- `fixture-audit.log`
- scenario manifests and baseline/injection/verification/cleanup SQL
- relevant application source functions

For each scenario, expected entity/table/ground truth were compared with runtime entity diagnostics, metadata choices, planned and executed SQL, debug-trace row counts, evidence-gate results, AI trace, orchestration decisions, and cleanup status.

The benchmark run's fixture audit is the fixture-validity evidence. A fresh audit was attempted during this review but timed out without a result and is not counted as passed. Live evaluation preflight passed. Existing affected tests passed 122/122.

## Required summary

| Scenario | Fixture Valid | Failure Stage | Primary Root Cause | Root Cause Proven? | Fix Required | Recommended Fix Area |
| -------- | ------------- | ------------- | ------------------ | ------------------ | ------------ | -------------------- |
| banking-benchmark-002 | Yes | Entity resolution | `APPLICATION_ENTITY_RESOLUTION_DEFECT` | Yes | Yes | Canonical/direct-extension resolution |
| banking-benchmark-010 | Yes | Evidence planning | `APPLICATION_EVIDENCE_PLANNING_DEFECT` | Yes | Yes | Correlated retry evidence planning |
| orders-benchmark-004 | Yes | Target selection | `APPLICATION_TARGET_SELECTION_DEFECT` | Yes | Yes | Explicit-entity target precedence |
| orders-benchmark-007 | Yes | Target selection | `APPLICATION_TARGET_SELECTION_DEFECT` | Yes | Yes | Database-proven table promotion |
| orders-benchmark-010 | Yes | Evidence planning | `APPLICATION_EVIDENCE_PLANNING_DEFECT` | Yes | Yes | Correlated retry evidence planning |
| shipping-benchmark-004 | Yes | Entity resolution | `APPLICATION_ENTITY_RESOLUTION_DEFECT` | Yes | Yes | Full-schema exact lookup/handoff |
| shipping-benchmark-005 | Yes | Evidence planning | `APPLICATION_EVIDENCE_PLANNING_DEFECT` | Yes | Yes | Correlation-aware duplicate evidence |
| shipping-benchmark-010 | Yes | Entity resolution | `APPLICATION_ENTITY_RESOLUTION_DEFECT` | Yes | Yes | Primary versus diagnostic candidates |
| shipping-benchmark-016 | Yes | Entity resolution | `APPLICATION_ENTITY_RESOLUTION_DEFECT` | Yes | Yes | Full-schema exact lookup/handoff |
| clinic-benchmark-007 | Yes | Target selection | `APPLICATION_TARGET_SELECTION_DEFECT` | Yes | Yes | Database-proven table promotion |
| clinic-benchmark-018 | Yes | Entity resolution | `APPLICATION_ENTITY_RESOLUTION_DEFECT` | Yes | Yes | Full-schema exact lookup/handoff |
| payroll-benchmark-004 | Yes | Target selection | `APPLICATION_TARGET_SELECTION_DEFECT` | Yes | Yes | Explicit-entity target precedence |
| payroll-benchmark-010 | Yes | Evidence planning | `APPLICATION_EVIDENCE_PLANNING_DEFECT` | Yes | Yes | Correlated retry evidence planning |

| Classification | Count |
| -------------------------------- | ----: |
| Confirmed application defect | 13 |
| Benchmark defect | 0 |
| Fixture defect | 0 |
| Configuration defect | 0 |
| Infrastructure defect | 0 |
| Expected evidence-gate rejection | 0 |
| Reporting/classification defect | 0 |
| Insufficient evidence | 0 |

## Scenario-by-scenario traces

### banking-benchmark-002

- Expected: partial `BNK-2026-0002` resolves to `BNK-2026-0002-A` in `eval.transfers`.
- Fixture: valid; correlation `EVAL-BANKING-102` verified.
- Actual: extraction succeeded. Resolution returned `ambiguous` with the primary `-A` row and prefixed `AUD-`, `EX-`, and `MSG-` identifiers competing as candidates.
- Downstream: metadata target selection, SQL, evidence gate, AI, and judge were skipped.
- Divergence: a unique direct canonical extension was not distinguished from related diagnostic identifiers.
- Source: `entity_resolution_service.py`: `resolve_entities`, `_resolve_one`, `_is_direct_canonical_extension`.
- Limitation: the terminal trace does not retain the full pre-resolution metadata input, so resolver ranking versus metadata handoff cannot be separated further without new diagnostics.

### banking-benchmark-010

- Expected: prove exhausted retries and a pending transfer.
- Actual: exact entity resolution; seven safe queries executed; `eval.transfers` returned entity rows.
- Missing: correlated retry/audit/exception evidence.
- Gate: correctly rejected only the reported condition.
- AI/Judge: skipped.
- Divergence: evidence plan proved identity but did not plan the evidence required by the retry claim.
- Source: `safe_sql_service.py`: `plan_safe_queries`.

### orders-benchmark-004

- Expected: resolve `ORD-2026-0004-A` in `eval.pick_tasks` and prove the correlated integration row is absent.
- Actual: intent was `PROCESS_FLOW_BREAK`, but target selection persisted `missing_target = downstream processing`; no identified entities, SQL, or evidence were produced.
- Divergence: a generic predicate phrase displaced the explicit identifier and affected object.
- Source: `chat.py`: `_run_dynamic_investigation`.

### orders-benchmark-007

- Expected: investigate `ORD-2026-0007-A` in `eval.receipts` with correlated exception evidence.
- Actual: exact resolution succeeded, but the primary plan targeted purchase/sales order tables. Seven queries returned no entity rows.
- Gate: correctly rejected missing key, rows, and condition.
- Divergence: the database-backed receipt table was not promoted after entity resolution.
- Source: `chat.py`: `_run_dynamic_investigation`.

### orders-benchmark-010

- Expected: prove retry exhaustion for `ORD-2026-0010-A`.
- Actual: exact resolution and entity rows in `sales_order_lines`; retry evidence absent.
- Gate: correctly rejected the unconfirmed condition.
- Divergence: diagnostic evidence was discovered but omitted from the executed plan.
- Source: `safe_sql_service.py`: `plan_safe_queries`.

### shipping-benchmark-004

- Expected: exact `SHP-2026-0004-A` in `eval.container_events`.
- Actual: `ENTITY_NOT_FOUND`, zero candidates, zero SQL.
- Divergence: a fixture-verified exact entity was not available to/returned by resolution.
- Source: `entity_resolution_service.py`: `resolve_entities`, `_resolve_one`.
- Limitation: runtime trace cannot distinguish lookup-target omission from lookup execution failure.

### shipping-benchmark-005

- Expected: primary milestone plus exactly two differently keyed processing messages sharing `EVAL-SHIPPING-105`.
- Actual: exact primary entity found. Eight queries proved the milestone but did not return the two integration messages. Duplicate queries looked for duplicate business keys rather than same-correlation events.
- Gate: correctly rejected affected rows, relationship, and duplicate condition.
- Divergence: correlation expansion did not bridge the primary row to differently keyed message rows.
- Source: `chat.py`: `_expand_related_id_evidence`, `_run_dynamic_investigation`.

### shipping-benchmark-010

- Expected: exact booking `SHP-2026-0010-A` and correlated retry evidence.
- Actual: resolution returned only `MSG-`, `EX-`, and `AUD-` identifiers and declared ambiguity. No SQL ran.
- Divergence: related diagnostic identifiers became primary candidates while the verified booking entity was not selected.
- Source: `entity_resolution_service.py`: `resolve_entities`, `_resolve_one`.

### shipping-benchmark-016

- Expected: exact `SHP-2026-0016-A` in `eval.bills_of_lading`, then overlapping correlation evidence.
- Actual: `ENTITY_NOT_FOUND`, zero candidates, zero SQL.
- Divergence: fixture-verified exact entity not returned by resolution.
- Source: `entity_resolution_service.py`: `resolve_entities`, `_resolve_one`.

### clinic-benchmark-007

- Expected: exact `CLN-2026-0007-A` in `eval.payments` with exception/compensation evidence.
- Actual: exact resolution succeeded; target plan used exceptions, patients, and insurance policies. Seven queries returned no rows.
- Gate: correctly rejected all missing proof.
- Divergence: database-proven payments target was not promoted.
- Source: `chat.py`: `_run_dynamic_investigation`.

### clinic-benchmark-018

- Expected: exact `CLN-2026-0018-A` in `eval.encounters` plus repeated same-correlation operation.
- Actual: `ENTITY_NOT_FOUND`, zero candidates, zero SQL.
- Divergence: fixture-verified exact entity not returned by resolution.
- Source: `entity_resolution_service.py`: `resolve_entities`, `_resolve_one`.

### payroll-benchmark-004

- Expected: exact `PAY-2026-0004-A` in `eval.time_entries` and absent downstream integration row.
- Actual: `missing_target = downstream processing`; no entity, SQL, or evidence.
- Divergence: generic wording displaced the explicit identifier.
- Source: `chat.py`: `_run_dynamic_investigation`.

### payroll-benchmark-010

- Expected: prove exhausted retries and pending `PAY-2026-0010-A`.
- Actual: exact `payroll_items` entity found; seven queries executed and two returned entity rows; retry evidence absent.
- Gate: correctly rejected the unconfirmed condition.
- Divergence: correlated diagnostic evidence was omitted.
- Source: `safe_sql_service.py`: `plan_safe_queries`.

Full stage objects, connection context, fixture paths, and evidence references are in `invalid-scenario-execution-traces.json`. Field-level comparison is in `invalid-scenario-root-cause-matrix.csv`.

## Cross-scenario patterns

1. Early resolution exits have no `debug_trace` metadata snapshot. The stage failure is proven, but its internal resolver-versus-metadata-handoff sub-cause is not fully observable.
2. Generic phrases such as `downstream processing` can override explicit business identifiers before resolution.
3. Exact resolution does not always cause the table containing that match to become the primary evidence target.
4. Retry plans prove entity existence but omit audit/exception/integration evidence.
5. Duplicate planning assumes duplicate business keys even where the modeled duplicate is two distinct messages under one correlation.
6. Evidence gates are conservative and correct given their inputs. Weakening them would hide upstream defects.
7. Invalid classification and judge skipping are correct evaluation behavior.

## Confirmed defects

- Entity-resolution terminal decisions inconsistent with fixture-verified entities: 5.
- Target-selection decisions inconsistent with explicit identifiers or database-proven tables: 4.
- Evidence plans insufficient for the declared retry/duplicate investigation intent: 4.

## Unconfirmed hypotheses

- Whether the three exact `not_found` cases originate specifically in metadata-table truncation, resolver lookup-target construction, or SQL lookup execution: insufficient retained trace to distinguish.
- Whether one shared code defect explains all five resolution cases: not proven.
- Whether correcting these defects will make all 13 pass deterministic or AI judging: not proven.
- Fresh dynamic fixture audit during this review: inconclusive because the command timed out; only the completed benchmark's successful audit is used.

## Recommended implementation order

1. Add generic pre-resolution diagnostics and correct entity resolution/full-schema handoff.
2. Correct explicit-identifier target precedence and database-proven table promotion.
3. Correct correlation-aware retry and duplicate evidence planning.
4. Rerun focused unit/integration tests.
5. Rerun only these 13 scenarios before authorizing 100 scenarios.

No evidence-gate or runner-validation change is recommended.

## Risks and regression areas

- New entity preference could incorrectly suppress genuine ambiguity.
- Full-schema promotion could broaden SQL planning and increase unsafe or irrelevant query candidates.
- Generic target precedence must work on unseen schemas without domain mappings.
- Diagnostic-table expansion could collect unrelated correlation rows.
- Retry terminology varies across unseen databases.
- Duplicate evidence must not equate shared correlation with duplication unless row/event evidence proves multiple operations.

## Verification commands

Executed successfully:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_entity_resolution_service.py tests/test_ai_and_databases.py tests/test_evaluation_runner.py tests/test_benchmark_phase2_reporting.py tests/test_official_validation_suite.py -q -p no:cacheprovider
```

Result: `122 passed`.

This set covers entity resolution, metadata discovery, SQL planning/safety, evidence gates, runner classification/reporting, and manifest structure.

Executed successfully:

```powershell
.\.venv\Scripts\python.exe -m evaluation.cli preflight
```

Result: all checks passed, including databases, migration head, worker, API, authentication, five application connections, read-only mode, manifests/scripts, judge/provider, allowlists, markers, and runtime isolation.

Attempted but not counted as passed:

```powershell
.\.venv\Scripts\python.exe scripts/evaluation/audit_sqlserver_fixtures.py --dynamic
```

Result: timed out without output during this review. The completed benchmark's `fixture-audit.log` records 125/125 valid and is the fixture evidence used here.

## GO/NO-GO recommendation

**GO for implementing shared, generic fixes in the order above. NO-GO for the 100-scenario benchmark until the 13 affected scenarios are scoreable or produce a genuinely expected evidence-gate outcome.**

Do not change scenarios, expected answers, scoring, AI-trace validation, or the evidence gate.
