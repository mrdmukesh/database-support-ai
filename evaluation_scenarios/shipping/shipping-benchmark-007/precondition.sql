SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[voyages] WHERE BusinessKey LIKE N'SHP-2026-0007%' OR CorrelationId=N'EVAL-SHIPPING-107') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
