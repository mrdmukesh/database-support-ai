SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-119';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-119';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-119';
DELETE FROM eval.[claims] WHERE BusinessKey LIKE N'CLN-2026-0019%';
INSERT eval.[claims](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0019-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-119');
COMMIT;
GO
