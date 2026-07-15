SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[bills_of_lading] WHERE BusinessKey LIKE N'SHP-2026-0008%' OR CorrelationId=N'EVAL-SHIPPING-108') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO
