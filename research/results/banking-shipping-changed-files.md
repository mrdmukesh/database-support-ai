# Changed-file summary

| File | Change |
|---|---|
| `src/legacydb_copilot/config.py` | Retry jitter, circuit threshold, and cooldown configuration |
| `src/legacydb_copilot/services/llm_reasoning_service.py` | Transient classification, bounded retry/backoff/jitter, circuit breaker, prospective HTTP diagnostics |
| `src/legacydb_copilot/services/evidence_focus_service.py` | Prefer unique database-proven entity table over generic nouns |
| `src/legacydb_copilot/services/evidence_gate_service.py` | Recognize shared correlation proof across distinct tables |
| `tests/test_llm_provider_retry.py` | Provider status, timeout, malformed-response, exhaustion, and circuit tests |
| `tests/test_banking_shipping_fixture_regressions.py` | Fixture, target provenance, and correlation regressions |
| `tests/test_evaluation_runner.py` | Resume reset-before-reinjection regression |
| Banking pilot-004 fixture SQL | Align injected and verified status with `Running` question |
| Banking benchmark-007 fixture SQL | Align injected and verified status with `Processing` question |
| Shipping benchmark-007 fixture SQL | Align injected and verified status with `Processing` question |
| `research/results/banking-shipping-*` | Analysis, comparison, blockers, tests, changed files, and commits |

No question, expected answer, release tag, credential, `.env` file, official benchmark result folder, or unrelated working-tree change was committed.
