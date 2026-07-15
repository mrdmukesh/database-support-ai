SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[leave_requests] WHERE BusinessKey LIKE N'PAY-2026-0016%' AND CorrelationId=N'EVAL-PAYROLL-116') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[leave_requests] WHERE BusinessKey LIKE N'PAY-2026-0016%';
GO
