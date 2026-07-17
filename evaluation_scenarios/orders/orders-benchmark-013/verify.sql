SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[shipments] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ORD-2026-0013-A' AND e.CorrelationId=N'EVAL-ORDERS-113') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[shipments] WHERE BusinessKey=N'ORD-2026-0013-A' AND CorrelationId=N'EVAL-ORDERS-113';
GO
