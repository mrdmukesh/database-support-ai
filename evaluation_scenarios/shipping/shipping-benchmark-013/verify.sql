SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[shipment_milestones] WHERE BusinessKey LIKE N'SHP-2026-0013%' AND CorrelationId=N'EVAL-SHIPPING-113') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[shipment_milestones] WHERE BusinessKey LIKE N'SHP-2026-0013%';
GO
