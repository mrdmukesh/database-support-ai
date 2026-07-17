SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[claims] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey LIKE N'CLN-2026-0003%' AND e.CorrelationId=N'EVAL-CLINIC-103') < 2 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[claims] WHERE BusinessKey LIKE N'CLN-2026-0003%' AND CorrelationId=N'EVAL-CLINIC-103';
GO
