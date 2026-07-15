SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[encounters] WHERE BusinessKey LIKE N'CLN-2026-0002%' OR CorrelationId=N'EVAL-CLINIC-102') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
