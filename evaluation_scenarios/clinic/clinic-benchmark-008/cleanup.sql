SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-108';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-108';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-108';
DELETE FROM eval.[procedures_performed] WHERE BusinessKey LIKE N'CLN-2026-0008%';
COMMIT;
GO
