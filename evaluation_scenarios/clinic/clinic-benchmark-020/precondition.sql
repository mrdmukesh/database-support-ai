SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[lab_orders] WHERE BusinessKey LIKE N'CLN-2026-0020%' OR CorrelationId=N'EVAL-CLINIC-120') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
