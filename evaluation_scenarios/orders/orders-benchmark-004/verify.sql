SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[pick_tasks] WHERE BusinessKey LIKE N'ORD-2026-0004%' AND CorrelationId=N'EVAL-ORDERS-104') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[pick_tasks] WHERE BusinessKey LIKE N'ORD-2026-0004%';
GO
