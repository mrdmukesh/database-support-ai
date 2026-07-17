SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[fraud_alerts] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'BNK-2026-0008-A' AND e.CorrelationId=N'EVAL-BANKING-108') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[fraud_alerts] WHERE BusinessKey=N'BNK-2026-0008-A' AND CorrelationId=N'EVAL-BANKING-108';
GO
