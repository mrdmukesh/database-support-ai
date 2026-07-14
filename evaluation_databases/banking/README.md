# Banking Operations synthetic evaluation database

Azure SQL-compatible, synthetic-only pilot database. No production-derived data is included.

## Workflows

1. Intake/master-data → operational transaction → completion.
2. External integration message → processing → audit/exception handling.
3. Batch processing → downstream record → reconciliation.

## Relationships

- `eval.customers` (root)
- `eval.accounts` → `eval.customers`
- `eval.account_balances` → `eval.accounts`
- `eval.transactions` → `eval.accounts`
- `eval.transfers` → `eval.accounts`
- `eval.beneficiaries` → `eval.customers`
- `eval.payment_instructions` → `eval.accounts`
- `eval.loans` → `eval.customers`
- `eval.loan_schedules` → `eval.loans`
- `eval.cards` → `eval.accounts`
- `eval.fraud_alerts` → `eval.transactions`
- `eval.compliance_cases` → `eval.customers`
- `eval.integration_messages` (root)
- `eval.batch_runs` (root)
- `eval.exceptions` (root)
- `eval.audit_history` (root)

## Objects

16 tables, 5 views, 8 stored procedures, one scalar function, one audit trigger, realistic PK/FK and status/time indexes.
