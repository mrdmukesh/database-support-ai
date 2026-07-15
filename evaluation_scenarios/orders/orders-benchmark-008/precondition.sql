SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[purchase_orders] WHERE BusinessKey LIKE N'ORD-2026-0008%' OR CorrelationId=N'EVAL-ORDERS-108') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
