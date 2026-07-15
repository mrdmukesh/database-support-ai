SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-119';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-119';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-119';
DELETE FROM eval.[claims] WHERE BusinessKey LIKE N'CLN-2026-0019%';
COMMIT;
GO
