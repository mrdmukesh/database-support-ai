SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-116';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-116';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-116';
DELETE FROM eval.[fraud_alerts] WHERE BusinessKey LIKE N'BNK-2026-0016%';
INSERT eval.[fraud_alerts](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0016-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-116');
COMMIT;
GO
