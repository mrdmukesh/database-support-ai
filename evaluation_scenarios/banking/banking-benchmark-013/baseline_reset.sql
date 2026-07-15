SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-BANKING-113';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-BANKING-113';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-BANKING-113';
DELETE FROM eval.[beneficiaries] WHERE BusinessKey LIKE N'BNK-2026-0013%';
INSERT eval.[beneficiaries](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0013-A',N'Ready',N'Clean benchmark baseline',N'EVAL-BANKING-113');
COMMIT;
GO
