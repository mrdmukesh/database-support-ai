SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-110';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-110';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-110';
DELETE FROM eval.[transfers] WHERE BusinessKey LIKE N'BNK-2026-0010%';
INSERT eval.[transfers](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0010-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-110');
COMMIT;
GO
