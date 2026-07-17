# Investigation Trace

## Scenario

- Scenario ID: shipping-pilot-001
- Investigation ID: INV-20260716-233319-22303681
- Question: Delivery is complete for shipment SHP-5001; why is the empty-return work order missing?
- Fixture validity: VALID
- Supported engine: sqlserver
- Actual engine: MySQL

## Pipeline

- Intent: MISSING_DATA
- Extracted entities: `[{"entity_type": "exact_id_or_code", "value": "SHP-5001"}, {"entity_type": "business_identifier", "value": "SHP-5001"}, {"entity_type": "possible_table_or_column", "value": "Delivery"}, {"entity_type": "possible_table_or_column", "value": "is"}, {"entity_type": "possible_table_or_column", "value": "complete"}, {"entity_type": "possible_table_or_column", "value": "for"}, {"entity_type": "possible_table_or_column", "value": "shipment"}, {"entity_type": "possible_column", "value": "SHP"}, {"entity_type": "possible_table_or_column", "value": "why"}, {"entity_type": "possible_table_or_column", "value": "the"}, {"entity_type": "possible_table_or_column", "value": "empty"}, {"entity_type": "possible_table_or_column", "value": "return"}, {"entity_type": "possible_table_or_column", "value": "work"}, {"entity_type": "possible_table_or_column", "value": "order"}, {"entity_type": "entity_resolution", "extracted_value": "SHP-5001", "matched_value": "SHP-5001", "match_type": "exact", "confidence": 1.0, "evidence_id": "ENTITY-1-EXACT-8", "candidates": [{"identifier": "SHP-5001", "metadata": {"Status": "Delivered"}, "evidence_id": "ENTITY-1-EXACT-8"}], "reason": "Exact database evidence match."}]`
- Metadata discovered: audit_history, batch_runs, bills_of_lading, bookings, carrier_assignments, container_assignments, container_events, container_master, customers, customs_holds, customs_releases, damage_reports, dangerous_goods, demurrage_detention, depots, empty_return_instructions, equipment_interchange, evaluation_marker, exceptions, gate_transactions, integration_messages, invoices, ports, rail_movements, reefer_readings, reefer_settings, repair_orders, shipment_milestones, shipments, terminals
- Candidate ranking: table:audit_history (column name relevance=1.5; outside top scored metadata candidates); table:batch_runs (column name relevance=1.5; outside top scored metadata candidates); table:empty_return_instructions (table name relevance=8; column name relevance=4.5); table:exceptions (column name relevance=1.5; outside top scored metadata candidates); table:integration_messages (column name relevance=1.5; outside top scored metadata candidates); table:repair_orders (table name relevance=4; column name relevance=3); table:shipment_milestones (table name relevance=4; column name relevance=4.5); table:shipments (table name relevance=4; column name relevance=3); table:transport_work_orders (table name relevance=8; column name relevance=6); table:truck_movements (column name relevance=4.5)
- SQL statements persisted/executed: 8
- Evidence records: 8
- Evidence gate: REJECTED
- AI reasoning invoked: False
- AI model: None
- Prompt version: None
- Application AI tokens: 0 input / 0 output
- Benchmark status: invalid_configuration

## SQL and row counts

```json
[
  {
    "sql": "SELECT TransportWorkOrdersId, ShipmentsId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM transport_work_orders WHERE (CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(Status AS CHAR) = 'SHP-5001')",
    "row_count": 0,
    "evidence_id": "SQL-1"
  },
  {
    "sql": "SELECT TransportWorkOrdersId, ShipmentsId, BusinessKey, Status, EventTime, Details, CorrelationId FROM transport_work_orders WHERE ((CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(Status AS CHAR) = 'SHP-5001')) AND TransportWorkOrdersId IS NULL",
    "row_count": 0,
    "evidence_id": "SQL-2"
  },
  {
    "sql": "SELECT IsActive, TransportWorkOrdersId, ShipmentsId, BusinessKey, Status, EventTime, Details, CorrelationId FROM transport_work_orders WHERE ((CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(Status AS CHAR) = 'SHP-5001')) AND IsActive IS NULL",
    "row_count": 0,
    "evidence_id": "SQL-3"
  },
  {
    "sql": "SELECT ShipmentsId, TransportWorkOrdersId, BusinessKey, Status, EventTime, Details, CorrelationId FROM transport_work_orders WHERE ((CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(Status AS CHAR) = 'SHP-5001')) AND ShipmentsId IS NULL",
    "row_count": 0,
    "evidence_id": "SQL-4"
  },
  {
    "sql": "SELECT EmptyReturnInstructionsId, ContainerAssignmentsId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM empty_return_instructions WHERE (CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(Status AS CHAR) = 'SHP-5001')",
    "row_count": 0,
    "evidence_id": "SQL-5"
  },
  {
    "sql": "SELECT EmptyReturnInstructionsId, ContainerAssignmentsId, BusinessKey, Status, EventTime, Details, CorrelationId FROM empty_return_instructions WHERE ((CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(Status AS CHAR) = 'SHP-5001')) AND EmptyReturnInstructionsId IS NULL",
    "row_count": 0,
    "evidence_id": "SQL-6"
  },
  {
    "sql": "SELECT IsActive, EmptyReturnInstructionsId, ContainerAssignmentsId, BusinessKey, Status, EventTime, Details, CorrelationId FROM empty_return_instructions WHERE ((CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(Status AS CHAR) = 'SHP-5001')) AND IsActive IS NULL",
    "row_count": 0,
    "evidence_id": "SQL-7"
  },
  {
    "sql": "SELECT ShipmentMilestonesId, ShipmentsId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM shipment_milestones WHERE (CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(Status AS CHAR) = 'SHP-5001')",
    "row_count": 0,
    "evidence_id": "SQL-8"
  }
]
```

## First remaining root cause

Metadata discovery omitted the expected transport_work_orders table even though fixture verification queried that table successfully. SQL planning therefore missed the expected downstream-absence evidence; the evidence gate marked the issue unreproduced, and that branch explicitly skipped enhance_reasoning_with_llm while still composing an AI_ANSWERED result.

Because the run is `INVALID_CONFIGURATION`, deterministic accuracy and AI Judge scoring were intentionally not published.
