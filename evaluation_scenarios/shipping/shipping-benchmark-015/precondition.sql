SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[voyages] WHERE BusinessKey LIKE N'SHP-2026-0015%' AND CorrelationId=N'EVAL-SHIPPING-115') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[voyages] WHERE BusinessKey LIKE N'SHP-2026-0015%';
GO
