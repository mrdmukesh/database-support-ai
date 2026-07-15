SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[container_events] WHERE BusinessKey LIKE N'SHP-2026-0020%' AND CorrelationId=N'EVAL-SHIPPING-120') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[container_events] WHERE BusinessKey LIKE N'SHP-2026-0020%';
GO
