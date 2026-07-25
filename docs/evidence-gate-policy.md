# Evidence Gate Policy

The evidence gate continues to block unsupported root-cause conclusions. A successful SQL statement or an
existing business entity is not, by itself, proof that a reported defect occurred.

## Decision modes

- **Root-cause mode:** A concrete reported condition (for example, a delay, duplicate, missing child, failed
  transition, or performance problem) must be reproduced by verified evidence before AI root-cause reasoning.
- **Evidence-summary mode:** A broad exploratory request that does not assert a concrete defect may be sent to
  the provider when the business key and relevant rows were verified. The prompt is constrained to a factual
  evidence/timeline summary, must say that no defect was reproduced, and may not infer a root cause. The result
  is classified `AI_SUMMARIZED_NOT_REPRODUCED`.
- **Blocked mode:** A concrete condition that was not reproduced remains
  `AI_SKIPPED_BY_EVIDENCE_GATE`. No provider request or fabricated invocation audit row is created.

This is policy B for exploratory investigations only. It does not relax SQL validation, read-only enforcement,
claim citation checks, tenant isolation, masking, or invocation auditing.

## Stable rule identifiers

- `EG-BUSINESS-KEY`: requested business key was not present in returned evidence.
- `EG-AFFECTED-ROWS`: no relevant verified row was returned.
- `EG-REPORTED-CONDITION`: the intent-specific defect/reproduction condition was not confirmed.
- `EG-RELATIONSHIP`: no relationship was confirmed through metadata, joins, or cross-table correlation.

Process-flow reproduction uses `PROCESS_FLOW_STATUS_OR_TRANSITION_CONFIRMED`. A broad request such as “identify
any delays” does not define a status value that can satisfy this rule, so it is eligible for constrained summary
mode when verified evidence exists. An assertion such as “shipment experienced delivery delays” still requires
delay evidence and remains blocked if that evidence is absent.

## Diagnostics

The persisted sanitized AI trace contains the complete `evidence_gate` decision, including the rule, expected and
actual values, evidence item count, successful SQL count, returned row count, blockers, and summary-mode
eligibility. Structured application logs include investigation/run ID, entity key, database name, SQL/evidence
counts, reproduction rule/result, failed rule, invocation decision, and skip reason. Raw row payloads and
credentials are not logged.

Relationship expansion uses the active schema's ID-bearing tables in addition to the ranked subset. Multiple
rows related by a booking or shipment ID are described as correlated rows; they are not labelled duplicates
unless a dedicated duplicate rule proves a repeated key/count.
