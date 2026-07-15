SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[transactions] WHERE BusinessKey LIKE N'BNK-2026-0009%' OR CorrelationId=N'EVAL-BANKING-109') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
