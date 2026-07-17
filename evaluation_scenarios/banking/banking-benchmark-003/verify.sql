SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[payment_instructions] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey LIKE N'BNK-2026-0003%' AND e.CorrelationId=N'EVAL-BANKING-103') < 2 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[payment_instructions] WHERE BusinessKey LIKE N'BNK-2026-0003%' AND CorrelationId=N'EVAL-BANKING-103';
GO
