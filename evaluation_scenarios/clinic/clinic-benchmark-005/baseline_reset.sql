SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-105';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-105';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-105';
DELETE FROM eval.[lab_results] WHERE BusinessKey LIKE N'CLN-2026-0005%';
INSERT eval.[lab_results](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0005-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-105');
COMMIT;
GO
