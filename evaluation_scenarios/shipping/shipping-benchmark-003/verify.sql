SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[container_assignments] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey LIKE N'SHP-2026-0003%' AND e.CorrelationId=N'EVAL-SHIPPING-103') < 2 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[container_assignments] WHERE BusinessKey LIKE N'SHP-2026-0003%' AND CorrelationId=N'EVAL-SHIPPING-103';
GO
