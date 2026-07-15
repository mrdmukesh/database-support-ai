SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[allocations] WHERE BusinessKey LIKE N'ORD-2026-0019%' OR CorrelationId=N'EVAL-ORDERS-119') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
