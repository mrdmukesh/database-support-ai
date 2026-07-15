SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[transport_work_orders] WHERE BusinessKey LIKE N'SHP-2026-0006%' AND CorrelationId=N'EVAL-SHIPPING-106') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[transport_work_orders] WHERE BusinessKey LIKE N'SHP-2026-0006%';
GO
