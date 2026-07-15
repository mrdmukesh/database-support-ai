SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-107';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-107';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-107';
DELETE FROM eval.[cards] WHERE BusinessKey LIKE N'BNK-2026-0007%';
INSERT eval.[cards](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0007-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-107');
COMMIT;
GO
