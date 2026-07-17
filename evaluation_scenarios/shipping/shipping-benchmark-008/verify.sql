SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[bills_of_lading] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'SHP-2026-0008-A' AND e.CorrelationId=N'EVAL-SHIPPING-108') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[bills_of_lading] WHERE BusinessKey=N'SHP-2026-0008-A' AND CorrelationId=N'EVAL-SHIPPING-108';
GO
