# Provider Timeout Investigation

## Finding

The release candidate made one 30-second OpenAI Responses API request and immediately fell back to deterministic reasoning for every exception. `shipping-benchmark-005` reached the provider, passed its evidence gate, then received `TimeoutError`; no retry occurred and no tokens were returned.

## Timeout hierarchy before correction

- Provider request: fixed 30 seconds in `llm_reasoning_service._call_openai_responses`.
- Provider retries: none.
- Evaluation API request: 60 seconds by default.
- Scenario terminal timeout: 600 seconds for the official run.
- Failure classification: sanitized `provider_failure` / `provider_request_or_response`; the evaluation runner then rejected zero token usage as `invalid_configuration`.

## Generic correction

Commit `11bbc5d` adds configurable, bounded provider reliability controls:

- `LLM_REQUEST_TIMEOUT_SECONDS=30`
- `LLM_RETRY_ATTEMPTS=2` (one retry)
- `LLM_RETRY_BACKOFF_SECONDS=0.5`
- `LLM_TOTAL_TIMEOUT_SECONDS=65`

Only `TimeoutError`, connection failures, and connection-level `URLError` are retryable. HTTP/provider request errors are terminal. The serialized request and grounded evidence payload are constructed once and reused unchanged. Cancellation (`KeyboardInterrupt`) is not caught. A monotonic total deadline bounds request time plus backoff. Persistence remains outside the request loop, so only one successful reasoning result can be persisted.

Debug traces record provider attempt count, retry count, per-attempt outcome, sanitized exception type, and final token usage. Exhausted retries remain a visible provider failure; no tokens or answers are fabricated.

## Validation

Focused tests cover timeout-then-success, repeated timeout, non-retryable HTTP error, unchanged request payload, single result consumption, total deadline, cancellation, and attempt audit fields.

The first operational five-run set was rejected because the shared editable virtual environment imported source from the original repository. It is preserved under `research/results/validation25-residual-investigation/shipping-005-repeated` and is not correction evidence.

After explicitly pinning `PYTHONPATH` to the corrected worktree and proving repository/API/worker commit `ab7787294f30e134f7dc0fb25a1a896f9dc22596`, five valid targeted runs completed:

| Run | Status | Gate | AI | Attempts | Retries | Cleanup |
|---|---|---|---|---:|---:|---|
| 1 | completed | passed | answered | 1 | 0 | passed |
| 2 | completed | passed | answered | 1 | 0 | passed |
| 3 | completed | passed | answered | 1 | 0 | passed |
| 4 | completed | passed | answered | 1 | 0 | passed |
| 5 | completed | passed | answered | 1 | 0 | passed |

No live run needed the retry, so transient recovery is proven by deterministic regression tests while live stability is 5/5.
