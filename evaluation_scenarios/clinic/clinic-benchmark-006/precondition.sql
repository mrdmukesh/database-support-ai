SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[prescriptions] WHERE BusinessKey LIKE N'CLN-2026-0006%' AND CorrelationId=N'EVAL-CLINIC-106') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[prescriptions] WHERE BusinessKey LIKE N'CLN-2026-0006%';
GO
