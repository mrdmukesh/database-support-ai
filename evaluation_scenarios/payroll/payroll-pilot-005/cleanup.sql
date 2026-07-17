SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-PAYROLL-005';
UPDATE eval.[tax_filings] SET BusinessKey=N'PAYROLL-012',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-PAYROLL' WHERE BusinessKey=N'TAX-2026-07' AND CorrelationId=N'EVAL-PAYROLL-005';
COMMIT;
GO
