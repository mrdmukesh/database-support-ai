SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-104';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-104';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-104';
DELETE FROM eval.[lab_orders] WHERE BusinessKey LIKE N'CLN-2026-0004%';
COMMIT;
GO
