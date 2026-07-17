SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[sales_orders] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ORD-2026-0017-A' AND e.CorrelationId=N'EVAL-ORDERS-117') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[sales_orders] WHERE BusinessKey=N'ORD-2026-0017-A' AND CorrelationId=N'EVAL-ORDERS-117';
GO
