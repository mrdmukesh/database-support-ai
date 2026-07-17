# Investigation Trace

## Scenario

- Scenario ID: shipping-pilot-001
- Investigation ID: INV-20260716-235234-32AE0108
- Question: Delivery is complete for shipment SHP-5001; why is the empty-return work order missing?
- Fixture validity: VALID
- Supported engine: sqlserver
- Actual engine: MySQL

## Pipeline

- Intent: MISSING_DATA
- Extracted entities: `[{"entity_type": "exact_id_or_code", "value": "SHP-5001"}, {"entity_type": "business_identifier", "value": "SHP-5001"}, {"entity_type": "possible_table_or_column", "value": "Delivery"}, {"entity_type": "possible_table_or_column", "value": "is"}, {"entity_type": "possible_table_or_column", "value": "complete"}, {"entity_type": "possible_table_or_column", "value": "for"}, {"entity_type": "possible_table_or_column", "value": "shipment"}, {"entity_type": "possible_column", "value": "SHP"}, {"entity_type": "possible_table_or_column", "value": "why"}, {"entity_type": "possible_table_or_column", "value": "the"}, {"entity_type": "possible_table_or_column", "value": "empty"}, {"entity_type": "possible_table_or_column", "value": "return"}, {"entity_type": "possible_table_or_column", "value": "work"}, {"entity_type": "possible_table_or_column", "value": "order"}, {"entity_type": "entity_resolution", "extracted_value": "SHP-5001", "matched_value": "SHP-5001", "match_type": "exact", "confidence": 1.0, "evidence_id": "ENTITY-1-EXACT-8", "candidates": [{"identifier": "SHP-5001", "metadata": {"Status": "Delivered"}, "evidence_id": "ENTITY-1-EXACT-8"}], "reason": "Exact database evidence match."}]`
- Metadata discovered: ['audit_history', 'batch_runs', 'bills_of_lading', 'bookings', 'carrier_assignments', 'container_assignments', 'container_events', 'container_master', 'customers', 'customs_holds', 'customs_releases', 'damage_reports', 'dangerous_goods', 'demurrage_detention', 'depots', 'empty_return_instructions', 'equipment_interchange', 'evaluation_marker', 'exceptions', 'gate_transactions', 'integration_messages', 'invoices', 'ports', 'rail_movements', 'reefer_readings', 'reefer_settings', 'repair_orders', 'shipment_milestones', 'shipments', 'terminals', 'transport_work_orders', 'truck_movements', 'vessel_movements', 'vessels', 'voyages']
- Candidate ranking: [{'object_type': 'table', 'name': '[MASKED_PII]', 'score': 32.4, 'reason': 'Matched 3 question/entity token(s); operational metadata signals: event, status field, timestamp field; selected from main problem phrase target; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 21.9, 'reason': 'Matched 2 question/entity token(s); operational metadata signals: event, status field, timestamp field; selected from main problem phrase parent; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 12.899999999999999, 'reason': 'Matched 1 question/entity token(s); operational metadata signals: event, status field, timestamp field; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 11.399999999999999, 'reason': 'Matched 1 question/entity token(s); operational metadata signals: event, status field, timestamp field; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 11.399999999999999, 'reason': 'Matched 1 question/entity token(s); operational metadata signals: event, status field, timestamp field; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 9.9, 'reason': 'Matched 2 question/entity token(s); operational metadata signals: event, status field, timestamp field; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 6.2, 'reason': 'Matched 0 question/entity token(s); operational metadata signals: event, integration, message, status field, timestamp field; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 6.2, 'reason': 'Matched 0 question/entity token(s); operational metadata signals: audit, event, history, status field, timestamp field; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 5.550000000000001, 'reason': 'Matched 0 question/entity token(s); operational metadata signals: event, exception, status field, timestamp field; has indexes'}, {'object_type': 'table', 'name': '[MASKED_PII]', 'score': 5.550000000000001, 'reason': 'Matched 0 question/entity token(s); operational metadata signals: batch, event, status field, timestamp field; has indexes'}]
- SQL statements persisted/executed: 8
- Evidence records: 8
- Evidence gate: REJECTED
- AI reasoning invoked: False
- AI model: [MASKED_PII]
- Prompt version: evidence-grounded-v1
- Application AI tokens: 0 input / 0 output
- Benchmark status: invalid_configuration

## SQL and row counts

```json
[
  {
    "sql": "SELECT ShipmentsId, BusinessKey, Status FROM shipment_milestones WHERE BusinessKey = 'SHP-5001'",
    "row_count": 0,
    "evidence_id": "SQL-1"
  },
  {
    "sql": "SELECT c.TransportWorkOrdersId, c.ShipmentsId, c.BusinessKey, c.Status, c.CorrelationId FROM shipment_milestones p JOIN transport_work_orders c ON c.ShipmentsId = p.ShipmentsId WHERE p.BusinessKey = 'SHP-5001'",
    "row_count": 0,
    "evidence_id": "SQL-2"
  },
  {
    "sql": "SELECT\n    p.BusinessKey AS parent_reference,\n    p.Status AS parent_status,\n    NULL AS child_reference,\n    CASE\n        WHEN c.TransportWorkOrdersId IS NULL THEN 'MISSING_RELATED_RECORD'\n        ELSE 'OK'\n    END AS issue_type\nFROM shipment_milestones p\nLEFT JOIN transport_work_orders c ON c.ShipmentsId = p.ShipmentsId AND (LOWER(CAST(c.BusinessKey AS CHAR)) LIKE '%work%' OR LOWER(CAST(c.Details AS CHAR)) LIKE '%work%') AND (LOWER(CAST(c.BusinessKey AS CHAR)) LIKE '%order%' OR LOWER(CAST(c.Details AS CHAR)) LIKE '%order%') AND (LOWER(CAST(c.BusinessKey AS CHAR)) LIKE '%return%' OR LOWER(CAST(c.Details AS CHAR)) LIKE '%return%')\nWHERE c.TransportWorkOrdersId IS NULL AND p.BusinessKey = 'SHP-5001'\nORDER BY p.BusinessKey",
    "row_count": 0,
    "evidence_id": "SQL-3"
  },
  {
    "sql": "SELECT\n    issue_type,\n    COUNT(*) AS issue_count,\n    MIN(parent_reference) AS example_parent\nFROM (\n    SELECT\n        p.BusinessKey AS parent_reference,\n        CASE\n            WHEN c.TransportWorkOrdersId IS NULL THEN 'MISSING_RELATED_RECORD'\n            ELSE 'OK'\n        END AS issue_type\n    FROM shipment_milestones p\n    LEFT JOIN transport_work_orders c\n        ON c.ShipmentsId = p.ShipmentsId AND (LOWER(CAST(c.BusinessKey AS CHAR)) LIKE '%work%' OR LOWER(CAST(c.Details AS CHAR)) LIKE '%work%') AND (LOWER(CAST(c.BusinessKey AS CHAR)) LIKE '%order%' OR LOWER(CAST(c.Details AS CHAR)) LIKE '%order%') AND (LOWER(CAST(c.BusinessKey AS CHAR)) LIKE '%return%' OR LOWER(CAST(c.Details AS CHAR)) LIKE '%return%')\n    WHERE c.TransportWorkOrdersId IS NULL AND p.BusinessKey = 'SHP-5001'\n) missing_related_candidates\nGROUP BY issue_type\nORDER BY issue_count DESC",
    "row_count": 0,
    "evidence_id": "SQL-4"
  },
  {
    "sql": "SELECT IntegrationMessagesId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM integration_messages WHERE CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(CorrelationId AS CHAR) = 'SHP-5001' OR LOWER(CAST(IntegrationMessagesId AS CHAR)) LIKE '%work%' OR LOWER(CAST(IntegrationMessagesId AS CHAR)) LIKE '%order%' OR LOWER(CAST(IntegrationMessagesId AS CHAR)) LIKE '%missing%' OR LOWER(CAST(IntegrationMessagesId AS CHAR)) LIKE '%absent%' OR LOWER(CAST(IntegrationMessagesId AS CHAR)) LIKE '%failed%' OR LOWER(CAST(Details AS CHAR)) LIKE '%work%' OR LOWER(CAST(Details AS CHAR)) LIKE '%order%' OR LOWER(CAST(Details AS CHAR)) LIKE '%missing%' OR LOWER(CAST(Details AS CHAR)) LIKE '%absent%' OR LOWER(CAST(Details AS CHAR)) LIKE '%failed%'",
    "row_count": 5,
    "evidence_id": "SQL-5"
  },
  {
    "sql": "SELECT ExceptionsId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM exceptions WHERE CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(CorrelationId AS CHAR) = 'SHP-5001' OR LOWER(CAST(Details AS CHAR)) LIKE '%work%' OR LOWER(CAST(Details AS CHAR)) LIKE '%order%' OR LOWER(CAST(Details AS CHAR)) LIKE '%missing%' OR LOWER(CAST(Details AS CHAR)) LIKE '%absent%' OR LOWER(CAST(Details AS CHAR)) LIKE '%failed%'",
    "row_count": 1,
    "evidence_id": "SQL-6"
  },
  {
    "sql": "SELECT BatchRunsId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM batch_runs WHERE CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(CorrelationId AS CHAR) = 'SHP-5001' OR LOWER(CAST(Details AS CHAR)) LIKE '%work%' OR LOWER(CAST(Details AS CHAR)) LIKE '%order%' OR LOWER(CAST(Details AS CHAR)) LIKE '%missing%' OR LOWER(CAST(Details AS CHAR)) LIKE '%absent%' OR LOWER(CAST(Details AS CHAR)) LIKE '%failed%'",
    "row_count": 0,
    "evidence_id": "SQL-7"
  },
  {
    "sql": "SELECT AuditHistoryId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM audit_history WHERE CAST(BusinessKey AS CHAR) = 'SHP-5001' OR CAST(CorrelationId AS CHAR) = 'SHP-5001' OR LOWER(CAST(Details AS CHAR)) LIKE '%work%' OR LOWER(CAST(Details AS CHAR)) LIKE '%order%' OR LOWER(CAST(Details AS CHAR)) LIKE '%missing%' OR LOWER(CAST(Details AS CHAR)) LIKE '%absent%' OR LOWER(CAST(Details AS CHAR)) LIKE '%failed%'",
    "row_count": 3,
    "evidence_id": "SQL-8"
  }
]
```

## First remaining root cause

Metadata discovery and ranking included transport_work_orders, but relationship inference treated shipment_milestones as the parent because it shared ShipmentsId without owning that primary key. The resulting negative-evidence SQL searched shipment_milestones for SHP-5001, returned zero rows, and the evidence gate correctly skipped application AI reasoning.

Because the run is `INVALID_CONFIGURATION`, deterministic accuracy and AI Judge scoring were intentionally not published.
