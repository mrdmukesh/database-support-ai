SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[cards] WHERE BusinessKey LIKE N'BNK-2026-0007%' OR CorrelationId=N'EVAL-BANKING-107') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
