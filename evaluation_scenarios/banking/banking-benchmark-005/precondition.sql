SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[beneficiaries] WHERE BusinessKey LIKE N'BNK-2026-0005%' AND CorrelationId=N'EVAL-BANKING-105') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[beneficiaries] WHERE BusinessKey LIKE N'BNK-2026-0005%';
GO
