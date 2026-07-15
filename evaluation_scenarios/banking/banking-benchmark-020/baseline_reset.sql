SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-120';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-120';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-120';
DELETE FROM eval.[accounts] WHERE BusinessKey LIKE N'BNK-2026-0020%';
INSERT eval.[accounts](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0020-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-120');
COMMIT;
GO
