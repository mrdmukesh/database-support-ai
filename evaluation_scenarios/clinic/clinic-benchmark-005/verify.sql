SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[lab_results] WHERE BusinessKey LIKE N'CLN-2026-0005%' AND CorrelationId=N'EVAL-CLINIC-105') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[lab_results] WHERE BusinessKey LIKE N'CLN-2026-0005%';
GO
