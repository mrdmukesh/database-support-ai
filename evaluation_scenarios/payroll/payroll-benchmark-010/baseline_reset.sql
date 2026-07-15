SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-110';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-110';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-110';
DELETE FROM eval.[payroll_items] WHERE BusinessKey LIKE N'PAY-2026-0010%';
INSERT eval.[payroll_items](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0010-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-110');
COMMIT;
GO
