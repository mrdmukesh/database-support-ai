SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-120';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-120';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-120';
DELETE FROM eval.[time_entries] WHERE BusinessKey LIKE N'PAY-2026-0020%';
INSERT eval.[time_entries](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0020-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-120');
COMMIT;
GO
