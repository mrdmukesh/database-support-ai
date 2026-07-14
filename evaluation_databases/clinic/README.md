# Clinic Operations synthetic evaluation database

Azure SQL-compatible, synthetic-only pilot database. No production-derived data is included.

## Workflows

1. Intake/master-data → operational transaction → completion.
2. External integration message → processing → audit/exception handling.
3. Batch processing → downstream record → reconciliation.

## Relationships

- `eval.clinics` (root)
- `eval.providers` → `eval.clinics`
- `eval.patients` (root)
- `eval.appointments` → `eval.patients`
- `eval.encounters` → `eval.appointments`
- `eval.diagnoses` → `eval.encounters`
- `eval.procedures_performed` → `eval.encounters`
- `eval.prescriptions` → `eval.encounters`
- `eval.lab_orders` → `eval.encounters`
- `eval.lab_results` → `eval.lab_orders`
- `eval.insurance_policies` → `eval.patients`
- `eval.claims` → `eval.encounters`
- `eval.payments` → `eval.claims`
- `eval.integration_messages` (root)
- `eval.exceptions` (root)
- `eval.audit_history` (root)

## Objects

16 tables, 5 views, 8 stored procedures, one scalar function, one audit trigger, realistic PK/FK and status/time indexes.
