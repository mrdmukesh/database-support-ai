SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-117';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-117';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-117';
DELETE FROM eval.[transactions] WHERE BusinessKey LIKE N'BNK-2026-0017%';
INSERT eval.[transactions](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0017-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-117');
COMMIT;
GO
