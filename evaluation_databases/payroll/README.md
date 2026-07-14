# Employee Payroll synthetic evaluation database

Azure SQL-compatible, synthetic-only pilot database. No production-derived data is included.

## Workflows

1. Intake/master-data → operational transaction → completion.
2. External integration message → processing → audit/exception handling.
3. Batch processing → downstream record → reconciliation.

## Relationships

- `eval.departments` (root)
- `eval.employees` → `eval.departments`
- `eval.employment_history` → `eval.employees`
- `eval.pay_groups` (root)
- `eval.pay_periods` → `eval.pay_groups`
- `eval.time_entries` → `eval.employees`
- `eval.leave_requests` → `eval.employees`
- `eval.payroll_runs` → `eval.pay_periods`
- `eval.payroll_items` → `eval.payroll_runs`
- `eval.deductions` → `eval.employees`
- `eval.payments` → `eval.payroll_items`
- `eval.tax_filings` → `eval.payroll_runs`
- `eval.integration_messages` (root)
- `eval.batch_runs` (root)
- `eval.exceptions` (root)
- `eval.audit_history` (root)

## Objects

16 tables, 5 views, 8 stored procedures, one scalar function, one audit trigger, realistic PK/FK and status/time indexes.
