SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[voyages] WHERE BusinessKey LIKE N'SHP-2026-0007%' AND CorrelationId=N'EVAL-SHIPPING-107') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[voyages] WHERE BusinessKey LIKE N'SHP-2026-0007%';
GO
