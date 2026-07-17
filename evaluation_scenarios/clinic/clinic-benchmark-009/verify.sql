SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[appointments] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'CLN-2026-0009-A' AND e.CorrelationId=N'EVAL-CLINIC-109') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[appointments] WHERE BusinessKey=N'CLN-2026-0009-A' AND CorrelationId=N'EVAL-CLINIC-109';
GO
