SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-101';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-101';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-101';
DELETE FROM eval.[payroll_runs] WHERE BusinessKey LIKE N'PAY-2026-0001%';
INSERT eval.[payroll_runs](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0001-A',N'Ready',N'Clean benchmark baseline',N'EVAL-PAYROLL-101');
COMMIT;
GO
