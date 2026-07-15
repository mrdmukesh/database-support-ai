SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[lab_orders] WHERE BusinessKey LIKE N'CLN-2026-0020%' AND CorrelationId=N'EVAL-CLINIC-120') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[lab_orders] WHERE BusinessKey LIKE N'CLN-2026-0020%';
GO
