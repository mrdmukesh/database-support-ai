SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[loans] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'BNK-2026-0014-A' AND e.CorrelationId=N'EVAL-BANKING-114') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[loans] WHERE BusinessKey=N'BNK-2026-0014-A' AND CorrelationId=N'EVAL-BANKING-114';
GO
