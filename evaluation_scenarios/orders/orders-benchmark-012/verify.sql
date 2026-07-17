SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[pick_tasks] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ORD-2026-0012-A' AND e.CorrelationId=N'EVAL-ORDERS-112') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[pick_tasks] WHERE BusinessKey=N'ORD-2026-0012-A' AND CorrelationId=N'EVAL-ORDERS-112';
GO
