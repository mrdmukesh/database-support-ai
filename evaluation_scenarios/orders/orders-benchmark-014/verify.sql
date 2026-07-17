SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[inventory_movements] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ORD-2026-0014-A' AND e.CorrelationId=N'EVAL-ORDERS-114') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[inventory_movements] WHERE BusinessKey=N'ORD-2026-0014-A' AND CorrelationId=N'EVAL-ORDERS-114';
GO
