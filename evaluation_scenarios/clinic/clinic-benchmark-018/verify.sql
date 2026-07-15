SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[encounters] WHERE BusinessKey LIKE N'CLN-2026-0018%' AND CorrelationId=N'EVAL-CLINIC-118') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[encounters] WHERE BusinessKey LIKE N'CLN-2026-0018%';
GO
