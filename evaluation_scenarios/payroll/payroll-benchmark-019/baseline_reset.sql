SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-119';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-119';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-119';
DELETE FROM eval.[payments] WHERE BusinessKey LIKE N'PAY-2026-0019%';
INSERT eval.[payments](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0019-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-119');
COMMIT;
GO
