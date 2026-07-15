SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[inventory_movements] WHERE BusinessKey LIKE N'ORD-2026-0006%' AND CorrelationId=N'EVAL-ORDERS-106') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[inventory_movements] WHERE BusinessKey LIKE N'ORD-2026-0006%';
GO
