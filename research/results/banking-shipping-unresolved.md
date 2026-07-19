# Unresolved Banking and Shipping issues

1. **HTTP status was not preserved in the official run.** The original 43 `HTTPError` records cannot retrospectively be classified as 429, 5xx, transient, or permanent. All 43 corresponding application scenarios completed in the focused reruns.
2. **Benchmark-003 evaluator mismatch.** Banking and Shipping safely reject ambiguous unsuffixed identifiers, consistent with the expected behavior, but the AI-required evaluator classifies the stop as insufficient evidence.
3. **Benchmark-013 procedure/fixture mismatch.** Banking's expected procedure writes loans rather than beneficiaries. Shipping's expected procedure writes voyages rather than shipment milestones, with no obvious workflow replacement. Benchmark-owner clarification is required before changing these contracts.

The seven Shipping Judge HTTP 429 failures are resolved: Judge-only version-2 scoring completed against the existing application evidence, and the latest-version aggregate is 23/23 completed. Recommendation: resolve or formally waive the four benchmark-003/013 application cases, then run the five-domain smoke test before authorizing a full 125-scenario rerun.
