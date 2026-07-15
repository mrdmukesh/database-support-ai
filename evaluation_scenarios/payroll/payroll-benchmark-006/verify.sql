SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[employees] WHERE BusinessKey LIKE N'PAY-2026-0006%' AND CorrelationId=N'EVAL-PAYROLL-106') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[employees] WHERE BusinessKey LIKE N'PAY-2026-0006%';
GO
