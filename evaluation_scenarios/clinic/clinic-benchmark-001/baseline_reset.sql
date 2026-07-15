SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-101';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-101';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-101';
DELETE FROM eval.[appointments] WHERE BusinessKey LIKE N'CLN-2026-0001%';
INSERT eval.[appointments](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0001-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-101');
COMMIT;
GO
