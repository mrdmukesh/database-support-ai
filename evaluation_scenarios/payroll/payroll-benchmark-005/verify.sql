SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[deductions] WHERE BusinessKey LIKE N'PAY-2026-0005%' AND CorrelationId=N'EVAL-PAYROLL-105') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[deductions] WHERE BusinessKey LIKE N'PAY-2026-0005%';
GO
