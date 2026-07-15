SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-104';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-104';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-104';
DELETE FROM eval.[lab_orders] WHERE BusinessKey LIKE N'CLN-2026-0004%';
INSERT eval.[lab_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0004-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-104');
COMMIT;
GO
