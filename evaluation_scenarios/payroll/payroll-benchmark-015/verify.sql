SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[tax_filings] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'PAY-2026-0015-A' AND e.CorrelationId=N'EVAL-PAYROLL-115') <> 1 THROW 51100, 'Benchmark entity/defect fixture invalid', 1;
SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[tax_filings] WHERE BusinessKey=N'PAY-2026-0015-A' AND CorrelationId=N'EVAL-PAYROLL-115';
GO
