SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[voyages] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'SHP-2026-0007-A' AND e.Status=N'Processing' AND e.CorrelationId=N'EVAL-SHIPPING-107') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[voyages] WHERE BusinessKey=N'SHP-2026-0007-A' AND CorrelationId=N'EVAL-SHIPPING-107';
GO
