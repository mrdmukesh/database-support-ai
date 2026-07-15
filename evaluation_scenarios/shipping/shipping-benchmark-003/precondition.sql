SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[container_assignments] WHERE BusinessKey LIKE N'SHP-2026-0003%' OR CorrelationId=N'EVAL-SHIPPING-103') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
