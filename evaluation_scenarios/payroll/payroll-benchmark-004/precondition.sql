SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[time_entries] WHERE BusinessKey LIKE N'PAY-2026-0004%' AND CorrelationId=N'EVAL-PAYROLL-104') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[time_entries] WHERE BusinessKey LIKE N'PAY-2026-0004%';
GO
