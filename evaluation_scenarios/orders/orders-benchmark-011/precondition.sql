SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[allocations] WHERE BusinessKey LIKE N'ORD-2026-0011%' AND CorrelationId=N'EVAL-ORDERS-111') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[allocations] WHERE BusinessKey LIKE N'ORD-2026-0011%';
GO
