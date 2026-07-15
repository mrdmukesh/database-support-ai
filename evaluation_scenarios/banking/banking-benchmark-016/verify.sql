SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[fraud_alerts] WHERE BusinessKey LIKE N'BNK-2026-0016%' AND CorrelationId=N'EVAL-BANKING-116') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[fraud_alerts] WHERE BusinessKey LIKE N'BNK-2026-0016%';
GO
