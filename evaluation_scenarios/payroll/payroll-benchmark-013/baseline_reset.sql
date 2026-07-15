SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-113';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-113';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-113';
DELETE FROM eval.[deductions] WHERE BusinessKey LIKE N'PAY-2026-0013%';
INSERT eval.[deductions](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0013-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-113');
COMMIT;
GO
