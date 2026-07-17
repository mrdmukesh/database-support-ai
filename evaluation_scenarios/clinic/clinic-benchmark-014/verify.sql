SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[prescriptions] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'CLN-2026-0014-A' AND e.CorrelationId=N'EVAL-CLINIC-114') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[prescriptions] WHERE BusinessKey=N'CLN-2026-0014-A' AND CorrelationId=N'EVAL-CLINIC-114';
GO
