SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[accounts] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'BNK-2026-0004-A' AND e.CorrelationId=N'EVAL-BANKING-104') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[accounts] WHERE BusinessKey=N'BNK-2026-0004-A' AND CorrelationId=N'EVAL-BANKING-104';
GO
