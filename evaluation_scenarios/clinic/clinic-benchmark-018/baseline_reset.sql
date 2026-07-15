SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-118';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-118';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-118';
DELETE FROM eval.[encounters] WHERE BusinessKey LIKE N'CLN-2026-0018%';
INSERT eval.[encounters](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0018-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-118');
COMMIT;
GO
