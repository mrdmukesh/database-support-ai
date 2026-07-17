SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[shipment_milestones] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'SHP-2026-0013-A' AND e.CorrelationId=N'EVAL-SHIPPING-113') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[shipment_milestones] WHERE BusinessKey=N'SHP-2026-0013-A' AND CorrelationId=N'EVAL-SHIPPING-113';
GO
