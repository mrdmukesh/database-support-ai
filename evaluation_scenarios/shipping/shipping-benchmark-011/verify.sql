SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[container_assignments] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'SHP-2026-0011-A' AND e.CorrelationId=N'EVAL-SHIPPING-111') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[container_assignments] WHERE BusinessKey=N'SHP-2026-0011-A' AND CorrelationId=N'EVAL-SHIPPING-111';
GO
