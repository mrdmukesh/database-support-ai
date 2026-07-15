SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[shipments] WHERE BusinessKey LIKE N'ORD-2026-0013%' AND CorrelationId=N'EVAL-ORDERS-113') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[shipments] WHERE BusinessKey LIKE N'ORD-2026-0013%';
GO
