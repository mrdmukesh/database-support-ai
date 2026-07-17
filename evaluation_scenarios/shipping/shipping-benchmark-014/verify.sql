SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[transport_work_orders] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'SHP-2026-0014-A' AND e.CorrelationId=N'EVAL-SHIPPING-114') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[transport_work_orders] WHERE BusinessKey=N'SHP-2026-0014-A' AND CorrelationId=N'EVAL-SHIPPING-114';
GO
