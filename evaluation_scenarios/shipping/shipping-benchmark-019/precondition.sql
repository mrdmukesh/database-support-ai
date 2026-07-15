SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[container_assignments] WHERE BusinessKey LIKE N'SHP-2026-0019%' AND CorrelationId=N'EVAL-SHIPPING-119') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[container_assignments] WHERE BusinessKey LIKE N'SHP-2026-0019%';
GO
