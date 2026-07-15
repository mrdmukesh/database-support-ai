SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[accounts] WHERE BusinessKey LIKE N'BNK-2026-0020%' AND CorrelationId=N'EVAL-BANKING-120') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[accounts] WHERE BusinessKey LIKE N'BNK-2026-0020%';
GO
