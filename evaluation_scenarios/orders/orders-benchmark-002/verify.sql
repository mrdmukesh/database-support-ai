SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[sales_order_lines] WHERE BusinessKey LIKE N'ORD-2026-0002%' AND CorrelationId=N'EVAL-ORDERS-102') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[sales_order_lines] WHERE BusinessKey LIKE N'ORD-2026-0002%';
GO
