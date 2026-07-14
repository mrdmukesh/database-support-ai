# Order and Inventory Management synthetic evaluation database

Azure SQL-compatible, synthetic-only pilot database. No production-derived data is included.

## Workflows

1. Intake/master-data → operational transaction → completion.
2. External integration message → processing → audit/exception handling.
3. Batch processing → downstream record → reconciliation.

## Relationships

- `eval.customers` (root)
- `eval.products` (root)
- `eval.warehouses` (root)
- `eval.inventory_balances` → `eval.products`
- `eval.inventory_movements` → `eval.inventory_balances`
- `eval.sales_orders` → `eval.customers`
- `eval.sales_order_lines` → `eval.sales_orders`
- `eval.allocations` → `eval.sales_order_lines`
- `eval.pick_tasks` → `eval.allocations`
- `eval.shipments` → `eval.sales_orders`
- `eval.purchase_orders` (root)
- `eval.purchase_order_lines` → `eval.purchase_orders`
- `eval.receipts` → `eval.purchase_orders`
- `eval.integration_messages` (root)
- `eval.batch_runs` (root)
- `eval.exceptions` (root)
- `eval.audit_history` (root)

## Objects

17 tables, 5 views, 8 stored procedures, one scalar function, one audit trigger, realistic PK/FK and status/time indexes.
