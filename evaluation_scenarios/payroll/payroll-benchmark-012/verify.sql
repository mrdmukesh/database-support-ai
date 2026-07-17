SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[time_entries] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'PAY-2026-0012-A' AND e.CorrelationId=N'EVAL-PAYROLL-112') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[time_entries] WHERE BusinessKey=N'PAY-2026-0012-A' AND CorrelationId=N'EVAL-PAYROLL-112';
GO
