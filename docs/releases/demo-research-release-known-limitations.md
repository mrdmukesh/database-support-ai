# Controlled demo and research release: known limitations

## Release classification

`CONTROLLED_DEMO_RESEARCH_RELEASE`

This release is restricted to stakeholder demonstrations, research evaluation,
analyst-assisted investigations, and controlled development or test environments. Human
review is mandatory. It is not autonomous diagnosis and is not production-ready.

## Protected validation baseline

Protected run `139aec7c-f934-461e-96ba-f25507555f62` executed 25 of 25 scenarios. All
25 received a passing aggregate deterministic classification. The deterministic average was
78.90%, and the AI judge average was 64.18%. The run recorded zero unsupported claims, safety
failures, critical failures, confidence failures, and evidence-integrity failures. Component
checks still found 16 response-type mismatches and 11 root-cause mismatches. These results must
be reported together; aggregate pass classifications do not erase component-level defects.

## Current strengths

- Evidence-grounded investigations and preserved citations
- LangGraph-controlled workflow with bounded execution state
- Central scan-policy auditing for SQL-derived evidence
- Verified contradiction rejection
- Zero unsupported claims, safety failures, critical failures, confidence failures, and
  evidence-integrity failures in the protected run
- Repeatable protected benchmark framework

## Known limitations

- The deterministic average is 78.90%, below the future 95% production target.
- Sixteen response-type mismatches and eleven root-cause mismatches remain.
- The AI judge average is 64.18%.
- Human review is mandatory for conclusions and remediation.
- The system must not be presented as autonomous production diagnosis.
- Benchmark coverage and accuracy require further expansion.
- Repository-wide Ruff debt remains outside this release.

## Pending scenario work

### Response-type mismatch only

`banking-benchmark-005`, `clinic-benchmark-006`, `shipping-benchmark-005`,
`banking-benchmark-011`, `payroll-benchmark-011`, `shipping-benchmark-008`, and
`clinic-benchmark-017`.

Observed behavior: evidence collection completed, but the public response contract did not match
the protected scenario contract. Likely cause: terminal evidence signals, reproduction state, and
response serialization are not normalized through one contract for every intent. Affected count:
7. Business risk: analysts may receive a correct evidence package under an incorrect conclusion
type. Future fix: centralize terminal response derivation across generated, persisted, serialized,
and scorer-normalized outputs. Regression requirement: one contract test per affected intent plus
persisted round-trip tests. Target milestone: accuracy milestone 1.

### Root-cause mismatch only

`orders-benchmark-007` and `clinic-benchmark-007`.

Observed behavior: response type matched, but the expected causal concept was not localized in a
verified claim. Likely cause: causal synthesis remains too generic when several relevant objects or
diagnostic rows are available. Affected count: 2. Business risk: an analyst may see relevant facts
without the decisive causal connection. Future fix: rank causal evidence by entity, transition,
time, and relationship, then verify the selected causal chain. Regression requirement: protected
concept-localization and evidence-reference tests. Target milestone: accuracy milestone 2.

### Response-type and root-cause mismatch

`shipping-benchmark-016`, `orders-benchmark-018`, `clinic-benchmark-018`,
`banking-benchmark-002`, `payroll-benchmark-001`, `banking-benchmark-016`,
`payroll-benchmark-016`, `orders-benchmark-001`, and `clinic-benchmark-001`.

Observed behavior: both terminal contract selection and causal conclusion missed their protected
checks. Likely cause: evidence obligations, object/relationship selection, and causal verification
diverge before final response normalization. Affected count: 9. Business risk: the report can
misstate both certainty and cause, requiring mandatory analyst intervention. Future fix: introduce
end-to-end evidence-obligation traces and require a verified causal chain before a confirmed
terminal response. Regression requirement: full lifecycle tests covering entity resolution,
objects, SQL, contradictions, response persistence, and scorer normalization. Target milestone:
accuracy milestone 3 and the 95% release gate.
