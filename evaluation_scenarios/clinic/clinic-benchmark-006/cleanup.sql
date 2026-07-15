SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-106';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-106';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-106';
DELETE FROM eval.[prescriptions] WHERE BusinessKey LIKE N'CLN-2026-0006%';
COMMIT;
GO
