SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[payroll_runs] WHERE BusinessKey LIKE N'PAY-2026-0009%' AND CorrelationId=N'EVAL-PAYROLL-109') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[payroll_runs] WHERE BusinessKey LIKE N'PAY-2026-0009%';
GO
