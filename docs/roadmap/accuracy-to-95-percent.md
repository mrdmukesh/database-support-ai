# Accuracy roadmap to 95 percent

The controlled demo/research baseline is 78.90% deterministic average with 16 response-type and
11 root-cause mismatches. Production readiness requires at least 95% deterministic accuracy, zero
unsupported claims, zero safety or critical failures, and successful evidence-integrity gates.

## 1. Response-type contract correction

Create one terminal response contract derived from reproduction, verified causal support,
execution success, contradictions, and evidence sufficiency. Validate generated, persisted,
serialized, and scorer-normalized forms. Exit criterion: zero response-type mismatches on the
protected 25 and focused contract tests for every intent.

## 2. Root-cause reasoning improvements

Rank entity-scoped causal chains across primary rows, relationships, diagnostic history, procedure
behavior, and time. Require cited verification and preserve conflicts. Exit criterion: zero
root-cause concept mismatches, no unsupported claims, and adversarial contradiction tests.

## 3. AI judge stability and score improvement

Align evidence packaging and report structure with the deterministic claim contract; investigate
judge inconsistency and mandatory-review signals without weakening rubrics. Exit criterion: stable
repeat scores, materially improved AI average, and no judge-critical disagreements.

## 4. Benchmark expansion

Add protected variants for ambiguity, multiple objects, missing relationships, NULL scope,
conflicting history, failed execution, and cross-domain terminology. Keep ground truth isolated.
Exit criterion: reviewed coverage matrix and deterministic repeatability across seeds/runs.

## 5. Repository-wide Ruff remediation

Pay down existing lint debt in bounded mechanical commits, independent from accuracy changes. Exit
criterion: repository-wide configured Ruff passes without broad ignores and without behavior drift.

## 6. Production-readiness evaluation

Run full tests, security review, migration/rollback drills, load and failure testing, tenant
isolation checks, human factors review, and the protected release benchmark. Exit criterion: at
least 95% deterministic accuracy and formal operational approval. Until then, human review remains
mandatory and deployments remain controlled.
