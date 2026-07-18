SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[beneficiaries] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'BNK-2026-0005-A' AND e.CorrelationId=N'EVAL-BANKING-105') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
IF (SELECT COUNT(*) FROM eval.integration_messages WHERE CorrelationId=N'EVAL-BANKING-105' AND BusinessKey IN (N'MSG-BNK-2026-0005-A-1',N'MSG-BNK-2026-0005-A-2')) <> 2 THROW 51102, 'Benchmark duplicate-message fixture invalid', 1;
IF (SELECT COUNT(DISTINCT BusinessKey) FROM eval.integration_messages WHERE CorrelationId=N'EVAL-BANKING-105') <> 2 THROW 51103, 'Benchmark messages must be distinct and correlated to one request', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[beneficiaries] WHERE BusinessKey=N'BNK-2026-0005-A' AND CorrelationId=N'EVAL-BANKING-105';
GO
