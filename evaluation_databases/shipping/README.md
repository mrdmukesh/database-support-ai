# Shipping and Container Operations synthetic evaluation database

Azure SQL-compatible, synthetic-only pilot database. No production-derived data is included.

## Workflows

1. Intake/master-data → operational transaction → completion.
2. External integration message → processing → audit/exception handling.
3. Batch processing → downstream record → reconciliation.

## Relationships

- `eval.customers` (root)
- `eval.bookings` → `eval.customers`
- `eval.shipments` → `eval.bookings`
- `eval.bills_of_lading` → `eval.shipments`
- `eval.container_master` (root)
- `eval.container_assignments` → `eval.shipments`
- `eval.vessels` (root)
- `eval.voyages` → `eval.vessels`
- `eval.ports` (root)
- `eval.terminals` → `eval.ports`
- `eval.depots` → `eval.ports`
- `eval.container_events` → `eval.container_assignments`
- `eval.shipment_milestones` → `eval.shipments`
- `eval.transport_work_orders` → `eval.shipments`
- `eval.carrier_assignments` → `eval.transport_work_orders`
- `eval.truck_movements` → `eval.transport_work_orders`
- `eval.rail_movements` → `eval.transport_work_orders`
- `eval.vessel_movements` → `eval.voyages`
- `eval.gate_transactions` → `eval.container_assignments`
- `eval.equipment_interchange` → `eval.gate_transactions`
- `eval.customs_holds` → `eval.shipments`
- `eval.customs_releases` → `eval.customs_holds`
- `eval.dangerous_goods` → `eval.shipments`
- `eval.reefer_settings` → `eval.container_assignments`
- `eval.reefer_readings` → `eval.reefer_settings`
- `eval.damage_reports` → `eval.container_assignments`
- `eval.repair_orders` → `eval.damage_reports`
- `eval.empty_return_instructions` → `eval.container_assignments`
- `eval.demurrage_detention` → `eval.container_assignments`
- `eval.invoices` → `eval.shipments`
- `eval.integration_messages` (root)
- `eval.batch_runs` (root)
- `eval.exceptions` (root)
- `eval.audit_history` (root)

## Objects

34 tables, 5 views, 8 stored procedures, one scalar function, one audit trigger, realistic PK/FK and status/time indexes.
