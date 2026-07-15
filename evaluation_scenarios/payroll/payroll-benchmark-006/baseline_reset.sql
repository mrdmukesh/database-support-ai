SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-106';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-106';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-106';
DELETE FROM eval.[employees] WHERE BusinessKey LIKE N'PAY-2026-0006%';
INSERT eval.[employees](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0006-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-106');
COMMIT;
GO
