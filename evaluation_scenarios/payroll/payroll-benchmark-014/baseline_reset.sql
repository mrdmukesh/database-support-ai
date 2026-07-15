SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-114';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-114';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-114';
DELETE FROM eval.[employees] WHERE BusinessKey LIKE N'PAY-2026-0014%';
INSERT eval.[employees](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0014-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-114');
COMMIT;
GO
