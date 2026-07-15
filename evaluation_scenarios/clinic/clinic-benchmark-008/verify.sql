SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[procedures_performed] WHERE BusinessKey LIKE N'CLN-2026-0008%' AND CorrelationId=N'EVAL-CLINIC-108') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[procedures_performed] WHERE BusinessKey LIKE N'CLN-2026-0008%';
GO
