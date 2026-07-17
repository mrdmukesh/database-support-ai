SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[payments] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey LIKE N'PAY-2026-0003%' AND e.CorrelationId=N'EVAL-PAYROLL-103') < 2 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[payments] WHERE BusinessKey LIKE N'PAY-2026-0003%' AND CorrelationId=N'EVAL-PAYROLL-103';
GO
