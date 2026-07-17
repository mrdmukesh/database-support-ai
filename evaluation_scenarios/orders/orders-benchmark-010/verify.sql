SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[sales_order_lines] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ORD-2026-0010-A' AND e.CorrelationId=N'EVAL-ORDERS-110') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[sales_order_lines] WHERE BusinessKey=N'ORD-2026-0010-A' AND CorrelationId=N'EVAL-ORDERS-110';
GO
