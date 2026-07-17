SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[payroll_runs] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'PAY-2026-0017-A' AND e.CorrelationId=N'EVAL-PAYROLL-117') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[payroll_runs] WHERE BusinessKey=N'PAY-2026-0017-A' AND CorrelationId=N'EVAL-PAYROLL-117';
GO
