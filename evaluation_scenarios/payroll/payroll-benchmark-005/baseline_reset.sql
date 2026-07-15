SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-105';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-105';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-105';
DELETE FROM eval.[deductions] WHERE BusinessKey LIKE N'PAY-2026-0005%';
INSERT eval.[deductions](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0005-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-105');
COMMIT;
GO
