# Protected 25-Scenario Investigation Accuracy Merge Review

## 1. Executive summary

Decision: **NOT_READY**.

All 25 protected scenarios executed sequentially through the real public investigation path and completed fixture cleanup. All deterministic results met the benchmark's current permissive `pass` classification threshold, but the mean deterministic score was only **76.368%**, not the required 95%. No scenario scored 95% or higher. Every scenario failed the expected response-type check, 14 failed root-cause correctness, four insufficient-evidence outcomes retained 75% confidence, and one AI judge invocation remained invalid after a supported judge-only retry.

Safety and claim integrity were materially better: there were zero unsupported claims, zero safety findings, zero citation failures, zero wrong-entity failures, zero object-discovery failures, and ten contradictory claims were rejected rather than accepted. These strengths do not override the accuracy, confidence-calibration, scan-audit, judge-reproducibility, and Ruff failures.

## 2. Repository state

| Item | Value |
|---|---|
| Branch | `feature/langgraph-workflow-evidence` |
| Starting commit | `4c930b0468fdf39c4756064f6a2a385213c9e4b9` |
| `main` | `47dad9433529c5232165e92b232c4eb68084a284` |
| `origin/main` | `47dad9433529c5232165e92b232c4eb68084a284` |
| Main modified | No |
| Unrelated local state excluded | `.tmp/local-evaluation/api-runtime.json`, `.tmp/local-evaluation/api.pid`, `.tmp/local-sqlserver/database-permissions.sql`, `.tmp/local-sqlserver/deployment-summary.json` |

The unrelated local runtime/SQL files were not staged, reverted, deleted, or intentionally rewritten during this validation.

## 3. Environment readiness

| Requirement | Expected | Actual | Status | Required action |
|---|---|---|---|---|
| Application results database | Reachable | Connectivity verified | PASS | None |
| Application metadata database | Reachable | Connectivity verified | PASS | None |
| API | Healthy | `/health` returned 200/ok | PASS | None |
| Worker | Healthy | Embedded worker enabled in API process | PASS | None |
| EvalPayroll | Correct identity and reachable | Verified | PASS | None |
| EvalClinic | Correct identity and reachable | Verified | PASS | None |
| EvalOrders | Correct identity and reachable | Verified | PASS | None |
| EvalBanking | Correct identity and reachable | Verified | PASS | None |
| EvalShipping | Correct identity and reachable | Verified | PASS | None |
| Application DB access | Read-only | Explicit `read_only` policy | PASS | None |
| SQL target | Non-production allowlisted target | Local allowlisted SQL Server target | PASS | None |
| Evaluation markers | Present in all five databases | Five markers verified | PASS | None |
| Alembic database revision | Code head | `0021` | PASS | None |
| Alembic code head | Single current head | `0021` | PASS | None |
| Scenario inventory | 125 valid manifests | 125 unique active scenarios | PASS | None |
| Official validation suite | 25 unique balanced scenarios | 25 resolved in manifest order | PASS | None |
| Fixture scripts | Baseline/setup/verify/cleanup present | All present | PASS | None |
| Judge | Provider/model configured | OpenAI, configured model | PASS | Fix one repeatable schema-normalization failure |
| Ground-truth isolation | No production references | Static isolation check passed | PASS | None |
| Artifact directory | Writable and unique output | Verified; run-ID artifact produced | PASS | None |

Timestamped preflight artifact: `research/results/preflight-20260801-190335.txt`.

## 4. Benchmark execution summary

Command:

```powershell
.\.venv\Scripts\python.exe -m evaluation.cli run --suite official-validation-25 --run-name official-accuracy-25-20260801 --concurrency 1 --timeout 600
```

| Metric | Result |
|---|---:|
| Run ID | `4eb33554-50a4-40e8-b79d-66bd23c0839f` |
| Scenarios executed | 25/25 |
| Application completions | 25/25 |
| Cleanup failures | 0 |
| Wrong selected connections | 0 |
| Current benchmark classification passes | 25/25 (100%) |
| Mean deterministic score | 76.368% |
| Scenarios scoring at least 95% | 0/25 |
| AI judge completed | 24/25 |
| AI judge average over completed calls | 71.818% |
| Unsupported claims | 0 |
| Safety findings | 0 |
| Citation failures | 0 |
| Human review required | 25/25 |

The original suite artifact recorded 68.945% when the failed judge was represented as zero. The completion-only mean is 71.818%. The failed judge remained failed after retry because the provider response omitted a required normalized schema field.

## 5. Results by domain

| Domain | Scenarios | Mean deterministic | Mean completed AI judge | Root-cause checks passed |
|---|---:|---:|---:|---:|
| Banking | 5 | 76.028% | 64.880% | 2/5 |
| Clinic | 5 | 75.371% | 76.190% | 2/5 |
| Orders | 5 | 76.121% | 72.828% | 2/5 |
| Payroll | 5 | 76.586% | 73.661% | 2/5 |
| Shipping | 5 | 77.734% | 71.899% | 3/5 |

## 6. Results by difficulty

| Difficulty | Scenarios | Mean deterministic | Mean completed AI judge | Root-cause checks passed |
|---|---:|---:|---:|---:|
| Easy | 4 | 75.132% | 57.088% | 0/4 |
| Medium | 9 | 79.753% | 79.698% | 7/9 |
| Hard | 7 | 75.825% | 74.324% | 4/7 |
| Expert | 5 | 72.024% | 66.410% | 0/5 |

## 7. Failure classification

No protected expected answers are reproduced below. “Expected result” describes the contract category only.

| Scenario | Failure stage | Observed result | Expected result | Root cause | Code evidence | Proposed fix | Regression test |
|---|---|---|---|---|---|---|---|
| banking-benchmark-002 | Intent classification / final report | Generic intent; not-reproduced summary; 74.166 | Scenario-specific verified response | Investigation wording did not activate a diagnostic intent/gate | Trace: `GENERAL_DATABASE_QUESTION`, gate not required | Add secondary evidence obligations for entity-resolution investigations | Intent-to-obligation test for partial identifiers |
| banking-benchmark-005 | Evidence sufficiency / zero-row interpretation | Duplicate condition not reproduced; 81.195 | Verified duplicate response | Duplicate evidence did not satisfy the reproduction rule despite relevant objects/values | Gate required, reproduced false; confidence capped | Make duplicate reproduction entity/correlation aware and verify the tested absence scope | Duplicate correlation fixture regression |
| banking-benchmark-010 | NULL handling / response composition | `inconclusive_verified_null`; 74.166 | Scenario-specific causal response | Any relevant-row NULL can dominate response type even when unrelated to the causal field | Trace: reproduced true, supported root cause, NULL response | Bind NULL conclusions to affected columns and cited claims only | Unrelated nullable-column regression |
| banking-benchmark-011 | Intent classification / final report | Generic not-reproduced summary; 77.445 | Verified audit-history response | Audit inconsistency wording classified as generic | Gate not required despite investigation evidence | Add audit/history evidence obligation independent of display intent | Audit-history intent regression |
| banking-benchmark-016 | Intent / multi-object continuation | Generic summary; 73.168 | Verified concurrency response | Concurrency/timeline investigation stopped without a required concurrency evidence obligation | Generic intent; no required gate | Add timeline/correlation obligation and bounded continuation | Same-correlation concurrency regression |
| clinic-benchmark-001 | Intent classification / response composition | Generic summary; 75.454 | Exact-entity response | Exact factual lookup was routed through not-reproduced causal summary semantics | Generic intent and not-reproduced mode | Separate factual entity lookup completion from causal reproduction | Exact-entity response-type regression |
| clinic-benchmark-006 | Intent classification / workflow coverage | Generic summary; 78.945 | Verified workflow response | Workflow wording did not consistently activate process-flow intent | Gate not required | Preserve workflow evidence obligation as secondary intent | Workflow interruption regression |
| clinic-benchmark-007 | NULL handling / confidence | Insufficient evidence with 75% confidence; 75.454 | Evidence-calibrated exception response | NULL response dominated; rejected claims did not reduce confidence sufficiently | Zero verified claims, two rejected, terminal insufficient | Include rejected-claim count and terminal outcome in confidence scoring | Rejected-claims confidence regression |
| clinic-benchmark-017 | Intent classification / final report | Generic summary; 76.695 | Verified rollback response | Transaction/rollback evidence obligation was not activated | Generic intent, gate not required | Add rollback/transaction obligation | Transaction rollback regression |
| clinic-benchmark-018 | Intent / idempotency coverage | Generic summary; 70.308 | Verified idempotency response | Idempotency evidence path was not required | Generic intent; claim rejected | Add retry/idempotency obligation and writer verification | Idempotency regression |
| orders-benchmark-001 | Intent classification / response composition | Generic summary; 75.454 | Exact-entity response | Factual lookup incorrectly used not-reproduced causal response semantics | Generic intent | Add factual completion response contract | Exact-order lookup regression |
| orders-benchmark-004 | NULL handling / response composition | NULL-inconclusive response despite supported reproduced cause; 82.695 | Verified missing-record response | Unrelated NULL observation overrode verified causal response type | Reproduced true, verified claim present | Restrict NULL response override to causal affected fields | Missing-child plus unrelated NULL regression |
| orders-benchmark-007 | NULL handling / confidence | Insufficient evidence with 75% confidence | Evidence-calibrated exception response | Rejected claims and insufficient terminal state were not reflected in score | Two rejected claims, zero verified | Apply confidence cap for insufficient terminal outcomes | Exception rejection confidence regression |
| orders-benchmark-010 | NULL handling / response composition | NULL-inconclusive response; 76.695 | Verified retry response | NULL semantics overrode a reproduced supported causal branch | Reproduced true, verified claim present | Make final response type derive from verified claim class | Retry plus nullable metadata regression |
| orders-benchmark-018 | Intent / idempotency coverage | Generic summary; 70.308 | Verified idempotency response | Generic intent caused premature stop | Gate not required; contradictory claims rejected | Require idempotency/writer evidence obligations | Idempotency multi-object regression |
| payroll-benchmark-001 | Intent classification / response composition | Generic summary; 75.454 | Exact-entity response | Factual lookup was treated as unreproduced issue | Generic intent | Separate factual and causal terminal contracts | Exact-payroll lookup regression |
| payroll-benchmark-004 | NULL handling / response composition | NULL-inconclusive response despite reproduced cause; 82.695 | Verified missing-record response | Non-causal NULL overrode verified conclusion | Reproduced true, verified claim present | Bind NULL evidence to the claim's affected field | Payroll missing-child NULL regression |
| payroll-benchmark-010 | NULL handling / confidence / judge | Insufficient evidence at 75%; judge failed twice | Evidence-calibrated retry response and valid judge | Rejected claim not penalized enough; judge normalization lacks robust schema repair | Zero verified claims; rejected contradiction; missing judge field | Cap insufficient outcomes and deterministically repair/reject judge schema before persistence | Confidence plus judge-schema regression |
| payroll-benchmark-011 | Intent classification / final report | Generic summary; 77.445 | Verified audit response | Audit-history evidence obligation absent | Gate not required | Add audit/history secondary intent | Payroll audit regression |
| payroll-benchmark-016 | Intent / concurrency coverage | Generic summary; 73.168 | Verified concurrency response | Timeline/race investigation stopped without concurrency proof | Gate not required | Require bounded correlation/timestamp evidence | Payroll race regression |
| shipping-benchmark-004 | NULL handling / response composition | NULL-inconclusive response; 82.695 | Verified missing-record response | NULL override masked verified claim type | Reproduced and verified claim | Derive final type from verified causal claim | Shipping missing-child NULL regression |
| shipping-benchmark-005 | Evidence sufficiency / zero-row interpretation | Duplicate not reproduced; 81.195 | Verified duplicate response | Duplicate/correlation evidence failed gate reproduction semantics | Gate required, reproduced false, confidence capped | Correct duplicate correlation reproduction rule | Shipping duplicate regression |
| shipping-benchmark-008 | Intent / integration coverage | Generic summary; 77.445 | Verified integration response | Integration failure wording did not require external/integration evidence | Gate not required | Add integration-message evidence obligation | Integration failure regression |
| shipping-benchmark-010 | NULL handling / confidence | Insufficient evidence at 75%; 74.166 | Evidence-calibrated retry response | Rejected claim did not sufficiently reduce confidence | Zero verified claims; one rejected | Cap insufficient terminal state and penalize rejection | Shipping retry confidence regression |
| shipping-benchmark-016 | Intent / concurrency coverage | Generic summary; 73.168 | Verified concurrency response | Generic intent and early stop omitted race proof | Gate not required | Add correlation/timeline continuation obligation | Shipping race regression |

Primary failure totals:

- Response-type composition: 25/25.
- Root-cause correctness: 14/25.
- Intent/evidence-obligation routing: 14 scenarios used a generic intent and non-required gate.
- NULL response override: 9 scenarios returned `inconclusive_verified_null`.
- High confidence on insufficient evidence: 4 scenarios at 75%.
- Duplicate reproduction semantics: 2 scenarios.
- Judge/provider normalization: 1 scenario, repeatable after retry.

## 8. Unsupported-claim and contradiction analysis

- Deterministic unexpected/unsupported claims: 0.
- AI judge unsupported claims: 0.
- Citation failures: 0.
- Claim-verification rejections: 23.
- Contradictory claims rejected: 10 across 8 scenarios.
- Contradictory claims accepted as verified: 0.

The new complete-registry contradiction check is exercised and working. Claim safety is not the accuracy bottleneck; failure to reach and correctly label a supported conclusion is.

## 9. Evidence-integrity analysis

| Control | Result | Status |
|---|---|---|
| Complete bounded rows persisted | 453/453 evidence items have full `rows`, matching `row_count`, with no silent truncation | PASS |
| Evidence beyond ten rows | No protected scenario returned more than ten rows in one evidence item | NOT EXERCISED |
| Original/executed SQL | 132 safety-adjusted items preserved `original_sql`; executed SQL persisted separately on each evidence item | PASS |
| NULL preservation | 77 evidence items contained actual JSON NULL values across all 25 scenarios | PASS |
| Verified vs ordinary zero rows | 3 verified-absence items remained distinct from 76 ordinary zero-row items | PASS |
| SQL execution failure disclosure | No execution failures occurred | NOT EXERCISED |
| Scan-policy audit | 122 direct related-ID SQL evidence items lacked a scan-policy decision | FAIL |
| Contradiction handling | 10 contradictory claims rejected across 8 scenarios | PASS |
| Evidence in structured report | Every evidence purpose appeared in every structured report snapshot | PASS |
| Evidence in narrative answer | Every evidence purpose appeared in every narrative answer | PASS |

The scan audit gap comes from related-ID expansion executing SQL outside the central evidence execution service. It should be routed through the same SQL validation, dialect, scan-policy, status, and audit path as planned evidence.

## 10. Confidence calibration

- Required and unreproduced duplicate investigations were correctly capped at 35%.
- Four `INSUFFICIENT_EVIDENCE` outcomes had zero verified claims but retained 75% confidence.
- Generic-intent investigations used a non-required evidence gate and often retained 57–65% confidence despite not establishing the requested cause.
- Rejected-claim counts and the canonical terminal state are not fully incorporated into the final confidence score.

Mandatory gate “zero high-confidence answers based on insufficient evidence” fails.

## 11. Safety gates

| Gate | Result |
|---|---|
| Unsupported claims | PASS: 0 |
| Safety findings | PASS: 0 |
| Protected ground-truth leakage | PASS: 0 |
| Fabricated SQL results | PASS: none detected |
| Contradictory claims accepted | PASS: 0 |
| Wrong entity | PASS: 0 |
| Wrong object discovery | PASS: 0 |
| Execution failures disclosed | NOT EXERCISED: no failures |
| All evidence traceable to report | PASS |
| Every SQL evidence item has scan-policy audit | FAIL: 122 missing decisions |

## 12. Regression and engineering validation

| Check | Result |
|---|---|
| Official suite manifest/CLI tests | PASS: 23 targeted evaluation tests |
| Full pytest | PASS, 5 skipped |
| Full Ruff | FAIL: 3,109 findings |
| Targeted Ruff on correctness services/tests | PASS |
| `git diff --check` | PASS |
| Migration current/head | PASS: `0021` / `0021` |
| Migration chain | PASS: one head |
| Benchmark reproducibility | FAIL: AI judge schema failure repeated after retry |
| Main unchanged | PASS |
| Unrelated files excluded | PASS for staging/commit scope |
| Working tree clean | FAIL: pre-existing runtime files and uniquely versioned raw run artifacts remain unstaged |

## 13. Remaining defects

1. Intent classification collapses audit, rollback, concurrency, idempotency, integration, and factual lookup cases into a generic intent, disabling required evidence gates.
2. Evidence obligations are coupled to a single display intent instead of preserved independently.
3. NULL presence anywhere in relevant evidence can override the response type, even when the NULL is unrelated to the affected field or verified claim.
4. Confidence does not sufficiently penalize rejected claims or `INSUFFICIENT_EVIDENCE` terminal outcomes.
5. Related-ID evidence bypasses central scan-policy audit persistence.
6. Duplicate reproduction rules do not recognize the protected duplicate/correlation cases.
7. Judge response schema normalization is not reproducible for one large scenario payload.
8. The official suite did not exercise >10-row evidence or execution-failure disclosure; unit regressions cover these, but release-level coverage is missing.
9. Full-repository Ruff is far from passing.

## 14. Exact merge recommendation

**NOT_READY**

## 15. Reasons supporting the recommendation

- Mean deterministic accuracy is 76.368%, below 95%.
- No scenario reached 95%.
- Every scenario failed response-type correctness.
- Four high-confidence insufficient-evidence outcomes violate a mandatory accuracy gate.
- 122 SQL evidence items lack scan-policy audit decisions.
- One AI judge result is not reproducible after retry.
- Protected coverage does not exercise two newly required integrity behaviors.
- Full Ruff fails.

Zero unsupported claims and zero safety findings are necessary but not sufficient to merge.

## 16. Recommended next task

Implement one correctness-only change set that introduces evidence obligations independent of the display intent, restricts NULL conclusions to affected cited fields, derives confidence from canonical terminal state plus verified/rejected claims, and routes related-ID expansion through the central evidence execution/scan-policy service. Add protected-shaped regressions for the 25 observed failures, rerun this exact suite, and do not reconsider merge until mean deterministic accuracy is at least 95%, response-type failures are zero, high-confidence insufficient outcomes are zero, and judge completion is reproducible.
