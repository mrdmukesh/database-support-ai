SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[payments] WHERE BusinessKey LIKE N'PAY-2026-0011%' AND CorrelationId=N'EVAL-PAYROLL-111') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[payments] WHERE BusinessKey LIKE N'PAY-2026-0011%';
GO
