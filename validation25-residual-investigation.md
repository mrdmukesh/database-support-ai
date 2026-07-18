# Validation-25 Residual Investigation

## Executive summary

The three residual risks have independent dispositions:

1. `banking-benchmark-005` is a benchmark-fixture contradiction. The question asserts two processing messages, but the fixture inserts one. The unchanged evidence gate correctly blocks the unsupported duplicate claim. No banking production change is justified.
2. `shipping-benchmark-005` exposed the absence of a retry for transient provider timeouts. A generic one-retry policy with bounded exponential backoff, total deadline, unchanged payload, and attempt observability was implemented.
3. The validation launcher relied on PowerShell 7-style array member enumeration. Explicit validated enumeration now works under Windows PowerShell 5.1 strict mode.

## Workstream A — banking evidence

Question claim → two processing messages represent one business request.

Required proof → two distinct rows in the processing-message table connected to the primary entity by the same correlation identifier.

Fixture → baseline plus injection creates two beneficiary rows with the same business key, but injection creates exactly one `eval.integration_messages` row. Verification checks only one beneficiary-to-exception join and does not verify two messages.

Execution → thirteen read-only statements ran. Exact primary lookup returned one beneficiary. Duplicate-message queries returned zero rows. Correlation expansion returned one message, one exception, one audit row, and one beneficiary.

Packaging → the duplicate queries and correlated message row were retained as SQL evidence with row counts and samples.

Gate → business key and affected rows passed; duplicate condition failed. The relationship flag was true in stored inputs, although a legacy blocking message also said the relationship was unconfirmed. That diagnostic inconsistency does not change the decisive missing second message.

Decision → `BENCHMARK_DEFECT` / genuine `EVIDENCE_INSUFFICIENT`. Keep the gate unchanged. A separate benchmark-only correction should either add and verify a second correlated message or rewrite the question/expectation to match one message. Benchmark files were not changed because this task did not approve that correction.

The evaluation runner's `invalid_configuration` label remains semantically coarse, but changing benchmark status semantics would alter evaluation behavior and pass accounting. It is recorded as a reporting backlog rather than changed here.

## Workstream B — provider reliability

Root cause: a single fixed 30-second call with no transient retry. Commit `11bbc5d` implements one bounded retry for connection-level failures. It does not retry evidence-gate rejection, deterministic validation, safety rejection, HTTP request errors, or cancellation. Five provenance-valid targeted runs completed 5/5; all gates, AI results, and cleanups passed.

Rejected alternatives: indefinite retries, fabricated token metadata, converting provider failures to passes, prompt mutation, retrying non-transient responses, or increasing the 600-second scenario timeout.

## Workstream C — PowerShell compatibility

Root cause: `$Scenarios.domain` depends on implicit array member enumeration unavailable under Windows PowerShell 5.1 strict mode. Commit `ab77872` uses explicit validated enumeration. The official 25 IDs resolve in exact manifest order. PowerShell 7 was unavailable locally.

## Validation

- Focused regression suite: passed.
- Complete automated suite: 900 passed, 0 failed, 5 skipped, terminal exit 0.
- Dynamic fixture audit: 125 valid, 0 invalid, 0 verification failures, 0 manifest mismatches.
- Targeted shipping runs: 5/5 completed, AI answered, cleanup passed.
- Banking rerun: not required because banking application behavior did not change.
- Official validation-25/full 125: not run.

## Residual risks and recommendation

The banking fixture contradiction still prevents a clean confirmation validation until a benchmark-only decision is approved. PowerShell 7 remains untested locally. Provider retry recovery is unit-tested but the five live calls all succeeded on attempt one, so no live transient timeout occurred.

Recommendation: correct or explicitly accept the banking benchmark contradiction, then perform a validation-25 confirmation run before the full 125.
