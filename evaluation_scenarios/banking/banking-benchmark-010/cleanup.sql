SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-110';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-110';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-110';
DELETE FROM eval.[transfers] WHERE BusinessKey LIKE N'BNK-2026-0010%';
COMMIT;
GO
