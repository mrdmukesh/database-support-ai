SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-107';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-107';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-107';
DELETE FROM eval.[tax_filings] WHERE BusinessKey LIKE N'PAY-2026-0007%';
INSERT eval.[tax_filings](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0007-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-107');
COMMIT;
GO
