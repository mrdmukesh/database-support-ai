SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-111';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-111';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-111';
DELETE FROM eval.[payment_instructions] WHERE BusinessKey LIKE N'BNK-2026-0011%';
INSERT eval.[payment_instructions](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0011-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-111');
COMMIT;
GO
