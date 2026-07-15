SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[allocations] WHERE BusinessKey LIKE N'ORD-2026-0003%' AND CorrelationId=N'EVAL-ORDERS-103') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[allocations] WHERE BusinessKey LIKE N'ORD-2026-0003%';
GO
