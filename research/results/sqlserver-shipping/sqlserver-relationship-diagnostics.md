# SQL Server Relationship Diagnostics

## Authoritative shipping relationship

- Child: `eval.transport_work_orders.ShipmentsId`
- Parent: `eval.shipments.ShipmentsId`
- Constraint: `FK__transport__Shipm__73BA3083`
- Source: `DECLARED_FOREIGN_KEY`
- Confidence: 1.0
- Accepted: yes

Declared SQL Server foreign keys now take priority over inferred relationships. CorrelationId and BusinessKey are excluded from inference. `shipment_milestones.ShipmentsId` is rejected as a parent key because `shipment_milestones` does not own that primary key.
