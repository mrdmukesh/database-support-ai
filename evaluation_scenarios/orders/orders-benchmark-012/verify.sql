SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[pick_tasks] WHERE BusinessKey LIKE N'ORD-2026-0012%' AND CorrelationId=N'EVAL-ORDERS-112') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[pick_tasks] WHERE BusinessKey LIKE N'ORD-2026-0012%';
GO
