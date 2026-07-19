# Unresolved Banking and Shipping issues

1. **Controlled reruns are blocked.** Evaluation preflight reports worker PID 18664 not running and the application API unreachable. Connection inventory then fails for all domains. SQL targets, evaluation markers, manifests, scripts, Judge configuration, and artifact storage pass.
2. **HTTP status was not preserved in the official run.** The 43 `HTTPError` records cannot retrospectively be classified as 429, 5xx, transient, or permanent. New diagnostics apply only to future calls.
3. **Benchmark-003 evaluator mismatch.** Banking and Shipping safely reject ambiguous unsuffixed identifiers, consistent with the expected behavior, but the AI-required evaluator classifies the stop as insufficient evidence.
4. **Benchmark-013 procedure/fixture mismatch.** Banking's expected procedure writes loans rather than beneficiaries. Shipping's expected procedure writes voyages rather than shipment milestones, with no obvious workflow replacement. Benchmark-owner clarification is required before changing these contracts.
5. **No scenario-level after result exists.** Unit/regression validation passed, but application defects and corrected fixtures require controlled live reruns before a full 125-scenario run or a pass claim.

Recommendation: do not run the full 125-scenario benchmark yet. Restore the worker/API, pass preflight, rerun failed Banking scenarios, then failed Shipping scenarios, followed by both complete domains and the five-domain smoke test. A full rerun is justified only if those stages pass and benchmark-013 ownership is resolved or explicitly waived.
