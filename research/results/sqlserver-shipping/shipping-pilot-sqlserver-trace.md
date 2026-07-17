# Shipping Pilot SQL Server Trace

- Run: `e0691591-449f-4d19-a29c-96d06a418368`
- Investigation: `INV-20260717-001842-682DA085`
- Fixture: `VALID`
- Engine/database: SQL Server / EvalShipping
- Parent selected: `eval.shipments(ShipmentsId)`
- Child selected: `eval.transport_work_orders(ShipmentsId)`
- Evidence gate reproduced: `True`
- Application AI invoked: `True`
- Model: `gpt-4.1-mini`
- Prompt: `evidence-grounded-v1`
- Application tokens: 4563 input / 1301 output
- Provenance: `AI_ANSWERED`
- Deterministic score: 0.0 (unadjusted 92.778)
- AI Judge score: 0.0

## Evidence gate
```json
{
  "required": true,
  "reproduced": true,
  "business_key_exists": true,
  "reported_condition_exists": true,
  "affected_rows_exist": true,
  "parent_child_relationship_exists": true,
  "confirmed_facts": [
    "Supplied business key found in returned evidence: SHP-5001.",
    "Affected rows were returned by safe SQL evidence.",
    "Parent-child relationship was confirmed by metadata or join evidence.",
    "Reported condition was reproduced by returned evidence."
  ],
  "blocking_reasons": [],
  "missing_evidence": [],
  "status_interpretation": []
}
```

## SQL evidence
```json
[
  {
    "evidence_id": "SQL-1",
    "purpose": "Verify upstream entity and current transition status",
    "sql": "SELECT ShipmentsId, BusinessKey, Status FROM eval.shipments WHERE BusinessKey = 'SHP-5001'",
    "row_count": 1,
    "error": null
  },
  {
    "evidence_id": "SQL-2",
    "purpose": "Check downstream records under expected or alternate identifiers",
    "sql": "SELECT c.TransportWorkOrdersId, c.ShipmentsId, c.BusinessKey, c.Status, c.CorrelationId FROM eval.shipments p JOIN eval.transport_work_orders c ON c.ShipmentsId = p.ShipmentsId WHERE p.BusinessKey = 'SHP-5001'",
    "row_count": 1,
    "error": null
  },
  {
    "evidence_id": "SQL-3",
    "purpose": "Confirmed Missing Related Record Candidates",
    "sql": "SELECT\n    p.BusinessKey AS parent_reference,\n    p.Status AS parent_status,\n    NULL AS child_reference,\n    CASE\n        WHEN c.TransportWorkOrdersId IS NULL THEN 'MISSING_RELATED_RECORD'\n        ELSE 'OK'\n    END AS issue_type\nFROM eval.shipments p\nLEFT JOIN eval.transport_work_orders c ON c.ShipmentsId = p.ShipmentsId AND (LOWER(CAST(c.BusinessKey AS NVARCHAR(MAX))) LIKE '%work%' OR LOWER(CAST(c.Details AS NVARCHAR(MAX))) LIKE '%work%') AND (LOWER(CAST(c.BusinessKey AS NVARCHAR(MAX))) LIKE '%order%' OR LOWER(CAST(c.Details AS NVARCHAR(MAX))) LIKE '%order%') AND (LOWER(CAST(c.BusinessKey AS NVARCHAR(MAX))) LIKE '%return%' OR LOWER(CAST(c.Details AS NVARCHAR(MAX))) LIKE '%return%')\nWHERE c.TransportWorkOrdersId IS NULL AND p.BusinessKey = 'SHP-5001'\nORDER BY p.BusinessKey",
    "row_count": 1,
    "error": null
  },
  {
    "evidence_id": "SQL-4",
    "purpose": "Missing Related Record Summary by Issue Type",
    "sql": "SELECT\n    issue_type,\n    COUNT(*) AS issue_count,\n    MIN(parent_reference) AS example_parent\nFROM (\n    SELECT\n        p.BusinessKey AS parent_reference,\n        CASE\n            WHEN c.TransportWorkOrdersId IS NULL THEN 'MISSING_RELATED_RECORD'\n            ELSE 'OK'\n        END AS issue_type\n    FROM eval.shipments p\n    LEFT JOIN eval.transport_work_orders c\n        ON c.ShipmentsId = p.ShipmentsId AND (LOWER(CAST(c.BusinessKey AS NVARCHAR(MAX))) LIKE '%work%' OR LOWER(CAST(c.Details AS NVARCHAR(MAX))) LIKE '%work%') AND (LOWER(CAST(c.BusinessKey AS NVARCHAR(MAX))) LIKE '%order%' OR LOWER(CAST(c.Details AS NVARCHAR(MAX))) LIKE '%order%') AND (LOWER(CAST(c.BusinessKey AS NVARCHAR(MAX))) LIKE '%return%' OR LOWER(CAST(c.Details AS NVARCHAR(MAX))) LIKE '%return%')\n    WHERE c.TransportWorkOrdersId IS NULL AND p.BusinessKey = 'SHP-5001'\n) missing_related_candidates\nGROUP BY issue_type\nORDER BY issue_count DESC",
    "row_count": 1,
    "error": null
  },
  {
    "evidence_id": "SQL-5",
    "purpose": "Inspect workflow exception, integration, audit, or batch evidence in eval.integration_messages",
    "sql": "SELECT IntegrationMessagesId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM eval.integration_messages WHERE CAST(BusinessKey AS NVARCHAR(MAX)) = 'SHP-5001' OR CAST(CorrelationId AS NVARCHAR(MAX)) = 'SHP-5001' OR LOWER(CAST(IntegrationMessagesId AS NVARCHAR(MAX))) LIKE '%work%' OR LOWER(CAST(IntegrationMessagesId AS NVARCHAR(MAX))) LIKE '%order%' OR LOWER(CAST(IntegrationMessagesId AS NVARCHAR(MAX))) LIKE '%missing%' OR LOWER(CAST(IntegrationMessagesId AS NVARCHAR(MAX))) LIKE '%absent%' OR LOWER(CAST(IntegrationMessagesId AS NVARCHAR(MAX))) LIKE '%failed%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%work%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%order%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%missing%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%absent%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%failed%'",
    "row_count": 5,
    "error": null
  },
  {
    "evidence_id": "SQL-6",
    "purpose": "Inspect workflow exception, integration, audit, or batch evidence in eval.exceptions",
    "sql": "SELECT ExceptionsId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM eval.exceptions WHERE CAST(BusinessKey AS NVARCHAR(MAX)) = 'SHP-5001' OR CAST(CorrelationId AS NVARCHAR(MAX)) = 'SHP-5001' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%work%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%order%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%missing%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%absent%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%failed%'",
    "row_count": 1,
    "error": null
  },
  {
    "evidence_id": "SQL-7",
    "purpose": "Inspect workflow exception, integration, audit, or batch evidence in eval.batch_runs",
    "sql": "SELECT BatchRunsId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM eval.batch_runs WHERE CAST(BusinessKey AS NVARCHAR(MAX)) = 'SHP-5001' OR CAST(CorrelationId AS NVARCHAR(MAX)) = 'SHP-5001' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%work%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%order%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%missing%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%absent%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%failed%'",
    "row_count": 0,
    "error": null
  },
  {
    "evidence_id": "SQL-8",
    "purpose": "Inspect workflow exception, integration, audit, or batch evidence in eval.audit_history",
    "sql": "SELECT AuditHistoryId, BusinessKey, Status, EventTime, Details, CorrelationId, IsActive FROM eval.audit_history WHERE CAST(BusinessKey AS NVARCHAR(MAX)) = 'SHP-5001' OR CAST(CorrelationId AS NVARCHAR(MAX)) = 'SHP-5001' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%work%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%order%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%missing%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%absent%' OR LOWER(CAST(Details AS NVARCHAR(MAX))) LIKE '%failed%'",
    "row_count": 3,
    "error": null
  }
]
```

## Remaining blocker
Entity validation treated internal resolution token entity-1-exact-8 as the investigated business entity, causing a critical override despite correct root cause, evidence, objects, citations, and 92.778 unadjusted score.
