SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-PAYROLL-108';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-PAYROLL-108';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-PAYROLL-108';
DELETE FROM eval.[leave_requests] WHERE BusinessKey LIKE N'PAY-2026-0008%';
COMMIT;
GO
