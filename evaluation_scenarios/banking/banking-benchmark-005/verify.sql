SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[beneficiaries] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'BNK-2026-0005-A' AND e.CorrelationId=N'EVAL-BANKING-105') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[beneficiaries] WHERE BusinessKey=N'BNK-2026-0005-A' AND CorrelationId=N'EVAL-BANKING-105';
GO
