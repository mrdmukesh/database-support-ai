SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[bills_of_lading] WHERE BusinessKey LIKE N'SHP-2026-0016%' AND CorrelationId=N'EVAL-SHIPPING-116') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[bills_of_lading] WHERE BusinessKey LIKE N'SHP-2026-0016%';
GO
