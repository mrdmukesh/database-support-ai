SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[tax_filings] WHERE BusinessKey=N'TAX-2026-07') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[tax_filings] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'TAX-2026-07' AND e.CorrelationId=N'EVAL-PAYROLL-005' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.tax_filings' EntityTable,N'BusinessKey' EntityColumn,N'TAX-2026-07' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[tax_filings] WHERE BusinessKey=N'TAX-2026-07';
GO
