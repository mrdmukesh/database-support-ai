SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[allocations] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ORD-2026-0011-A' AND e.CorrelationId=N'EVAL-ORDERS-111') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[allocations] WHERE BusinessKey=N'ORD-2026-0011-A' AND CorrelationId=N'EVAL-ORDERS-111';
GO
