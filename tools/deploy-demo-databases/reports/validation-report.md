# Demo Evaluation Databases V2 validation

## Package gate

PASS. Active text and XLSX XML contain zero legacy database names. Both JSON
metadata files parse. Each workbook contains exactly 500 expected logical
database-name substitutions and no other nonblank logical-value changes.

The five local `CreateDatabase.sql` files contain destructive database
operations and are explicitly excluded. Azure installation uses:

1. Tables
2. Foreign keys
3. Seed data
4. Views
5. Stored procedures
6. Functions
7. Triggers

## Azure execution

- Subscription: `MRDMUKESH` (`56ab486d-2488-4367-8b76-10e5aced04b7`)
- Resource group: `rg-database-support-ai-dev`
- Server: `sql-dsai-eval-56ab486d`
- Entra SQL connection to `master`: PASS
- `DemoBankingV2`: created and installed
- `DemoPayrollV2`: created and installed
- `DemoOrdersV2`: created and installed
- `DemoShippingV2`: created and installed
- `DemoClinicV2`: created and installed

Independent validation passed for all five databases. Every database has
18 tables, 18 primary keys, 252 indexes, 4 views, 3 stored procedures,
2 functions, and 1 trigger. Foreign-key counts are Banking 11, Payroll 8,
Orders 9, Shipping 10, and Clinic 10. Partition-row totals are Banking 9,542,
Payroll 9,145, Orders 9,505, Shipping 9,199, and Clinic 9,098.

Workspace registration, connection registration, metadata discovery, and smoke
investigations were not run because API authorization, organization ID, and a
secure database secret reference are not configured in this session.
