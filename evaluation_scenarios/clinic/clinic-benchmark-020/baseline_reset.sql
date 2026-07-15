SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-120';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-120';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-120';
DELETE FROM eval.[lab_orders] WHERE BusinessKey LIKE N'CLN-2026-0020%';
INSERT eval.[lab_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0020-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-120');
COMMIT;
GO
