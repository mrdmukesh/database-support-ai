SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-106';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-106';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-106';
DELETE FROM eval.[loans] WHERE BusinessKey LIKE N'BNK-2026-0006%';
INSERT eval.[loans](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0006-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-106');
COMMIT;
GO
