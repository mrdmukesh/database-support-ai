SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[container_events] WHERE BusinessKey LIKE N'SHP-2026-0020%' OR CorrelationId=N'EVAL-SHIPPING-120') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
