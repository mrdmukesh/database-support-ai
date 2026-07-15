SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-120';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-120';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-120';
DELETE FROM eval.[accounts] WHERE BusinessKey LIKE N'BNK-2026-0020%';
COMMIT;
GO
