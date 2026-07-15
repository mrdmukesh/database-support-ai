SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[prescriptions] WHERE BusinessKey LIKE N'CLN-2026-0006%' OR CorrelationId=N'EVAL-CLINIC-106') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
