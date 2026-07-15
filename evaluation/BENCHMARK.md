# AI Judge regression benchmark

The benchmark contains 125 scenarios: the original 25-scenario pilot plus 100
production-support regression scenarios. Ground truth and fixture SQL remain under
`evaluation_scenarios/`; production code receives only the natural-language question.

## Named suites

| Suite | Scenarios | Purpose |
|---|---:|---|
| Five-domain smoke | 5 | Fast deployment and connectivity check |
| Original pilot | 25 | Historical score comparison |
| Regression benchmark | 100 | Full category and difficulty coverage |
| Full release validation | 125 | Pilot plus regression release gate |

The Evaluation Dashboard supports these suites plus search, filters, previews, and
custom multi-selection. A 125-scenario run is deliberately executed with concurrency
1 per the evaluation safety policy and can take several hours.

## Distribution

| Domain | Easy | Medium | Hard | Expert | New | Total |
|---|---:|---:|---:|---:|---:|---:|
| Banking | 4 | 8 | 6 | 2 | 20 | 25 |
| Orders | 4 | 8 | 6 | 2 | 20 | 25 |
| Shipping | 4 | 8 | 6 | 2 | 20 | 25 |
| Payroll | 4 | 8 | 6 | 2 | 20 | 25 |
| Clinic | 4 | 8 | 6 | 2 | 20 | 25 |
| **New total** | **20** | **40** | **30** | **10** | **100** | **125 overall** |

## Validation

Run the offline contract and distribution gate:

```powershell
python -m pytest tests/test_benchmark_validator.py tests/test_evaluation_foundation.py -q
```

Run complete live infrastructure validation before a benchmark execution:

```powershell
python -m evaluation.cli preflight
```

The comparison reporter in `evaluation.reporting.comparison` groups before/after
results by domain, category, difficulty, release, model version, and AI Judge version;
it also calculates score changes, top failures, confidence, cost, duration, and
category regressions.

## Scenario inventory

The generated inventory below lists every scenario without exposing expected answers.

| Scenario | Domain | Category | Difficulty |
|---|---|---|---|
| banking-pilot-001 | banking | root_cause | medium |
| banking-pilot-002 | banking | root_cause | hard |
| banking-pilot-003 | banking | root_cause | hard |
| banking-pilot-004 | banking | root_cause | medium |
| banking-pilot-005 | banking | evidence_safety | hard |
| banking-benchmark-001 | banking | exact_entity_lookup | easy |
| banking-benchmark-002 | banking | partial_entity_resolution | easy |
| banking-benchmark-003 | banking | ambiguous_entity_resolution | hard |
| banking-benchmark-004 | banking | missing_downstream_record | medium |
| banking-benchmark-005 | banking | duplicate_transaction | medium |
| banking-benchmark-006 | banking | workflow_interruption | medium |
| banking-benchmark-007 | banking | exception_handling | medium |
| banking-benchmark-008 | banking | integration_failure | medium |
| banking-benchmark-009 | banking | queue_backlog | medium |
| banking-benchmark-010 | banking | retry_failure | hard |
| banking-benchmark-011 | banking | audit_history_inconsistency | hard |
| banking-benchmark-012 | banking | missing_reference_data | easy |
| banking-benchmark-013 | banking | stored_procedure_defect | hard |
| banking-benchmark-014 | banking | trigger_failure | hard |
| banking-benchmark-015 | banking | batch_processing_failure | medium |
| banking-benchmark-016 | banking | concurrency_race_condition | expert |
| banking-benchmark-017 | banking | transaction_rollback | hard |
| banking-benchmark-018 | banking | idempotency_issue | expert |
| banking-benchmark-019 | banking | incorrect_business_status | easy |
| banking-benchmark-020 | banking | multi_table_investigation | medium |
| orders-pilot-001 | orders | root_cause | medium |
| orders-pilot-002 | orders | root_cause | hard |
| orders-pilot-003 | orders | root_cause | hard |
| orders-pilot-004 | orders | root_cause | medium |
| orders-pilot-005 | orders | evidence_safety | hard |
| orders-benchmark-001 | orders | exact_entity_lookup | easy |
| orders-benchmark-002 | orders | partial_entity_resolution | easy |
| orders-benchmark-003 | orders | ambiguous_entity_resolution | hard |
| orders-benchmark-004 | orders | missing_downstream_record | medium |
| orders-benchmark-005 | orders | duplicate_transaction | medium |
| orders-benchmark-006 | orders | workflow_interruption | medium |
| orders-benchmark-007 | orders | exception_handling | medium |
| orders-benchmark-008 | orders | integration_failure | medium |
| orders-benchmark-009 | orders | queue_backlog | medium |
| orders-benchmark-010 | orders | retry_failure | hard |
| orders-benchmark-011 | orders | audit_history_inconsistency | hard |
| orders-benchmark-012 | orders | missing_reference_data | easy |
| orders-benchmark-013 | orders | stored_procedure_defect | hard |
| orders-benchmark-014 | orders | trigger_failure | hard |
| orders-benchmark-015 | orders | batch_processing_failure | medium |
| orders-benchmark-016 | orders | concurrency_race_condition | expert |
| orders-benchmark-017 | orders | transaction_rollback | hard |
| orders-benchmark-018 | orders | idempotency_issue | expert |
| orders-benchmark-019 | orders | incorrect_business_status | easy |
| orders-benchmark-020 | orders | multi_table_investigation | medium |
| shipping-pilot-001 | shipping | root_cause | medium |
| shipping-pilot-002 | shipping | root_cause | hard |
| shipping-pilot-003 | shipping | root_cause | hard |
| shipping-pilot-004 | shipping | root_cause | medium |
| shipping-pilot-005 | shipping | evidence_safety | hard |
| shipping-benchmark-001 | shipping | exact_entity_lookup | easy |
| shipping-benchmark-002 | shipping | partial_entity_resolution | easy |
| shipping-benchmark-003 | shipping | ambiguous_entity_resolution | hard |
| shipping-benchmark-004 | shipping | missing_downstream_record | medium |
| shipping-benchmark-005 | shipping | duplicate_transaction | medium |
| shipping-benchmark-006 | shipping | workflow_interruption | medium |
| shipping-benchmark-007 | shipping | exception_handling | medium |
| shipping-benchmark-008 | shipping | integration_failure | medium |
| shipping-benchmark-009 | shipping | queue_backlog | medium |
| shipping-benchmark-010 | shipping | retry_failure | hard |
| shipping-benchmark-011 | shipping | audit_history_inconsistency | hard |
| shipping-benchmark-012 | shipping | missing_reference_data | easy |
| shipping-benchmark-013 | shipping | stored_procedure_defect | hard |
| shipping-benchmark-014 | shipping | trigger_failure | hard |
| shipping-benchmark-015 | shipping | batch_processing_failure | medium |
| shipping-benchmark-016 | shipping | concurrency_race_condition | expert |
| shipping-benchmark-017 | shipping | transaction_rollback | hard |
| shipping-benchmark-018 | shipping | idempotency_issue | expert |
| shipping-benchmark-019 | shipping | incorrect_business_status | easy |
| shipping-benchmark-020 | shipping | multi_table_investigation | medium |
| payroll-pilot-001 | payroll | root_cause | medium |
| payroll-pilot-002 | payroll | root_cause | hard |
| payroll-pilot-003 | payroll | root_cause | hard |
| payroll-pilot-004 | payroll | root_cause | medium |
| payroll-pilot-005 | payroll | evidence_safety | hard |
| payroll-benchmark-001 | payroll | exact_entity_lookup | easy |
| payroll-benchmark-002 | payroll | partial_entity_resolution | easy |
| payroll-benchmark-003 | payroll | ambiguous_entity_resolution | hard |
| payroll-benchmark-004 | payroll | missing_downstream_record | medium |
| payroll-benchmark-005 | payroll | duplicate_transaction | medium |
| payroll-benchmark-006 | payroll | workflow_interruption | medium |
| payroll-benchmark-007 | payroll | exception_handling | medium |
| payroll-benchmark-008 | payroll | integration_failure | medium |
| payroll-benchmark-009 | payroll | queue_backlog | medium |
| payroll-benchmark-010 | payroll | retry_failure | hard |
| payroll-benchmark-011 | payroll | audit_history_inconsistency | hard |
| payroll-benchmark-012 | payroll | missing_reference_data | easy |
| payroll-benchmark-013 | payroll | stored_procedure_defect | hard |
| payroll-benchmark-014 | payroll | trigger_failure | hard |
| payroll-benchmark-015 | payroll | batch_processing_failure | medium |
| payroll-benchmark-016 | payroll | concurrency_race_condition | expert |
| payroll-benchmark-017 | payroll | transaction_rollback | hard |
| payroll-benchmark-018 | payroll | idempotency_issue | expert |
| payroll-benchmark-019 | payroll | incorrect_business_status | easy |
| payroll-benchmark-020 | payroll | multi_table_investigation | medium |
| clinic-pilot-001 | clinic | root_cause | medium |
| clinic-pilot-002 | clinic | root_cause | hard |
| clinic-pilot-003 | clinic | root_cause | hard |
| clinic-pilot-004 | clinic | root_cause | medium |
| clinic-pilot-005 | clinic | evidence_safety | hard |
| clinic-benchmark-001 | clinic | exact_entity_lookup | easy |
| clinic-benchmark-002 | clinic | partial_entity_resolution | easy |
| clinic-benchmark-003 | clinic | ambiguous_entity_resolution | hard |
| clinic-benchmark-004 | clinic | missing_downstream_record | medium |
| clinic-benchmark-005 | clinic | duplicate_transaction | medium |
| clinic-benchmark-006 | clinic | workflow_interruption | medium |
| clinic-benchmark-007 | clinic | exception_handling | medium |
| clinic-benchmark-008 | clinic | integration_failure | medium |
| clinic-benchmark-009 | clinic | queue_backlog | medium |
| clinic-benchmark-010 | clinic | retry_failure | hard |
| clinic-benchmark-011 | clinic | audit_history_inconsistency | hard |
| clinic-benchmark-012 | clinic | missing_reference_data | easy |
| clinic-benchmark-013 | clinic | stored_procedure_defect | hard |
| clinic-benchmark-014 | clinic | trigger_failure | hard |
| clinic-benchmark-015 | clinic | batch_processing_failure | medium |
| clinic-benchmark-016 | clinic | concurrency_race_condition | expert |
| clinic-benchmark-017 | clinic | transaction_rollback | hard |
| clinic-benchmark-018 | clinic | idempotency_issue | expert |
| clinic-benchmark-019 | clinic | incorrect_business_status | easy |
| clinic-benchmark-020 | clinic | multi_table_investigation | medium |
