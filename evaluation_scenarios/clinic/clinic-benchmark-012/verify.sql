SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[lab_orders] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'CLN-2026-0012-A' AND e.CorrelationId=N'EVAL-CLINIC-112') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[lab_orders] WHERE BusinessKey=N'CLN-2026-0012-A' AND CorrelationId=N'EVAL-CLINIC-112';
GO
