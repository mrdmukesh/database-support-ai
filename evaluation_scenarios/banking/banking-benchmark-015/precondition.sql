SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[cards] WHERE BusinessKey LIKE N'BNK-2026-0015%' OR CorrelationId=N'EVAL-BANKING-115') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
