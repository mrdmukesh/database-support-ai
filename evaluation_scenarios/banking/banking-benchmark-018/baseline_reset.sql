SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-118';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-118';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-118';
DELETE FROM eval.[transfers] WHERE BusinessKey LIKE N'BNK-2026-0018%';
INSERT eval.[transfers](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0018-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-118');
COMMIT;
GO
