SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[shipment_milestones] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'SHP-2026-0005-A' AND e.CorrelationId=N'EVAL-SHIPPING-105') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
IF (SELECT COUNT(*) FROM eval.integration_messages WHERE CorrelationId=N'EVAL-SHIPPING-105') <> 2 THROW 51101, 'Duplicate processing-message fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[shipment_milestones] WHERE BusinessKey=N'SHP-2026-0005-A' AND CorrelationId=N'EVAL-SHIPPING-105';
GO
