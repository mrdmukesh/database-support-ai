SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[bookings] WHERE BusinessKey LIKE N'SHP-2026-0002%' AND CorrelationId=N'EVAL-SHIPPING-102') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[bookings] WHERE BusinessKey LIKE N'SHP-2026-0002%';
GO
