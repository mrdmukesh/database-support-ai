SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM eval.[tax_filings] WHERE BusinessKey LIKE N'PAY-2026-0015%' AND CorrelationId=N'EVAL-PAYROLL-115') THROW 51100, 'Benchmark defect missing', 1;
SELECT N'verified' AS verification_status, BusinessKey, Status, CorrelationId FROM eval.[tax_filings] WHERE BusinessKey LIKE N'PAY-2026-0015%';
GO
