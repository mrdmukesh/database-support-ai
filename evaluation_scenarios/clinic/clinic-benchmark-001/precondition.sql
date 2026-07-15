SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[appointments] WHERE BusinessKey LIKE N'CLN-2026-0001%' OR CorrelationId=N'EVAL-CLINIC-101') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
