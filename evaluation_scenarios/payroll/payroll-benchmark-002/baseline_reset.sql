SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-102';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-102';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-102';
DELETE FROM eval.[payroll_items] WHERE BusinessKey LIKE N'PAY-2026-0002%';
INSERT eval.[payroll_items](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0002-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-102');
COMMIT;
GO
