SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[lab_results] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'CLN-2026-0013-A' AND e.CorrelationId=N'EVAL-CLINIC-113') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[lab_results] WHERE BusinessKey=N'CLN-2026-0013-A' AND CorrelationId=N'EVAL-CLINIC-113';
GO
