SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[transfers] WHERE BusinessKey LIKE N'BNK-2026-0010%' AND CorrelationId=N'EVAL-BANKING-110') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[transfers] WHERE BusinessKey LIKE N'BNK-2026-0010%';
GO
