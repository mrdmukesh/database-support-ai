SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-104';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-104';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-104';
DELETE FROM eval.[time_entries] WHERE BusinessKey LIKE N'PAY-2026-0004%';
INSERT eval.[time_entries](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0004-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-104');
COMMIT;
GO
