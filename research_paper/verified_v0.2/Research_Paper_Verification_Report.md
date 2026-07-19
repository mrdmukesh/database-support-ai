# Research Paper Verification Report

## Outcome

The draft was rebuilt as verified version 0.2 using the frozen release benchmark and the implemented repository. Submission-readiness status: **not ready for submission**. The paper is technically reviewable, but a stable-provider rerun, baseline experiments, and human evaluation are still missing.

## Evidence reviewed

- Frozen benchmark run `benchmark-125-d5815fd-20260718T155134Z` at commit `d5815fd509a13cb9dd3eec28c859c79f205d3c80` and tag `rc-v1.0-final`.
- Manifest SHA-256 `45CAC02D759FAC6B67C5B738A26B5BD23E4C3294EB3E4CC10000D4FC029B3F45` and artifact checksums.
- 125 scenario contracts and 625 lifecycle SQL scripts.
- Application agents, metadata/relationship services, SQL safety controls, evidence gate, LLM integration, report composition, authentication/tenancy, audit configuration, evaluation runner, deterministic validator, AI Judge, persistence, documentation, and selected tests/logs.

## Claims verified or corrected

- Strict pass: **46/125 = 36.8%** (95% Wilson CI 28.9%–45.5%).
- Conditional application accuracy: **48/51 = 94.12%** (95% Wilson CI 84.1%–98.0%).
- Provider failures: **55/125**, recorded as `HTTPError` / `PROVIDER_OTHER_FAILURE`; HTTP status was not retained.
- Evidence insufficient: **19/125**; application incorrect: **3/125**; judge failure: **2/125**.
- Requested/started/terminal/incomplete: **125/125/125/0**; cleanup and post-run fixture audit: **125/125**.
- Domain distribution: 25 each across payroll, clinic, orders, banking, and shipping.
- Difficulty distribution: medium 50, hard 45, easy 20, expert 10.
- AI Judge rubric: 30/25/10/10/10/10/5 over root cause, evidence, object discovery, fix, citation, safety, and completeness.

## Not verifiable / explicitly withheld

- The provider failure was caused by rate limiting (plausible, not proven).
- Production safety or production readiness.
- Superiority over baselines.
- Human-level quality or human agreement.
- Statistical significance against a pre-registered comparator.
- Billing cost (recorded zero is not a billing assertion).

## Test-status caveat

A fresh `pytest --collect-only -q` on 2026-07-19 enumerated more than 1,000 cases but was interrupted by `PermissionError` reading `.env.evaluation` in two evaluation modules. The paper therefore does not claim a clean current full-suite run. Frozen benchmark preflight, completion, cleanup, and fixture-audit evidence are reported separately.

## Missing experiments and future work

Stable-provider randomized rerun; persisted HTTP status/request IDs; baseline and ablation studies; blinded expert evaluation; AI Judge calibration; cross-engine replication; adversarial SQL-safety testing; and a pre-registered statistical plan.
