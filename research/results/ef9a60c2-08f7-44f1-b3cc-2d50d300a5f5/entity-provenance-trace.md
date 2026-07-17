# Shipping Entity-Provenance Quality Gate

The single authorized SQL Server rerun passed. No five-scenario pilot was started.

## Exact token-leak source

`InvestigationPersistenceReader.read()` loaded the mixed `extracted_entities_json` array into `identified_entities`. That array intentionally contained both extracted business entities and the resolver diagnostic object. `DeterministicValidator.validate()` then flattened the complete array and applied the business-identifier regex to every string. The resolver diagnostic `evidence_id` `ENTITY-1-EXACT-8` therefore entered `found_entities` and was treated as a second investigated business entity. The application had not replaced `SHP-5001`; the evaluator lost the type boundary.

## Boundary trace

| Boundary | Business value | Diagnostic value |
|---|---|---|
| User question | `SHP-5001` | — |
| Entity extraction | `SHP-5001` | — |
| Normalization | `SHP-5001` | — |
| Resolver result | `SHP-5001` | `ENTITY-1-EXACT-8` |
| Database resolution | `eval.shipments.BusinessKey = SHP-5001` | exact lookup, confidence 1.0 |
| Application serialization | typed `resolved_business_entity` | typed `entity_resolution_diagnostic` |
| Benchmark serialization | canonical `SHP-5001` | diagnostics-only object |
| Deterministic evaluator | `SHP-5001` | excluded from entity comparison |
| AI Judge payload | expected/investigated/evidence entity `SHP-5001` | separated diagnostics object |
| HTML/JSON report | canonical entity `SHP-5001`, validity `valid` | provenance retained in JSON |

Supporting evidence IDs: `ENTITY-1-EXACT-8`, `SQL-1`, `SQL-3`, `SQL-4`, and `SQL-6`.

## Result

- Run: `ef9a60c2-08f7-44f1-b3cc-2d50d300a5f5`
- Result row: `5aad8d6e-7c1a-47fb-aac1-a61f2e79ff39`
- Investigation: `INV-20260717-003426-351906D4`
- Fixture: VALID
- Evidence gate: accepted
- Application AI: invoked; `evidence-grounded-v1`; 4,563 input and 1,327 output tokens
- Application provenance: `AI_ANSWERED`
- Canonical investigated entity: `SHP-5001`
- Deterministic validation version: 2
- Unadjusted/final deterministic score: 93.055 / 93.055
- Critical overrides: none
- AI Judge: 92.15; no critical failure; no human review
- Judge prompt: `ai-judge-v2-entity-provenance`
- Benchmark validity: valid
- Duration: 27.576 seconds
- Cleanup: passed

The remaining score reduction is the rubric’s partial acceptable-fix match, not an entity-provenance failure.
