SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[sales_orders] WHERE BusinessKey LIKE N'ORD-2026-0009%' OR CorrelationId=N'EVAL-ORDERS-109') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
