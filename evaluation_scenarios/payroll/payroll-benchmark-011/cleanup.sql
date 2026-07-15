SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-111';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-111';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-111';
DELETE FROM eval.[payments] WHERE BusinessKey LIKE N'PAY-2026-0011%';
COMMIT;
GO
