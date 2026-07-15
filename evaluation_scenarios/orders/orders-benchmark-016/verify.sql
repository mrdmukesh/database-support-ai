SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[purchase_orders] WHERE BusinessKey LIKE N'ORD-2026-0016%' AND CorrelationId=N'EVAL-ORDERS-116') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[purchase_orders] WHERE BusinessKey LIKE N'ORD-2026-0016%';
GO
