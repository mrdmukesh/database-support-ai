SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-106';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-106';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-106';
DELETE FROM eval.[prescriptions] WHERE BusinessKey LIKE N'CLN-2026-0006%';
INSERT eval.[prescriptions](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0006-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-106');
COMMIT;
GO
