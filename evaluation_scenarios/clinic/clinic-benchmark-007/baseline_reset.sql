SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-107';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-107';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-107';
DELETE FROM eval.[payments] WHERE BusinessKey LIKE N'CLN-2026-0007%';
INSERT eval.[payments](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0007-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-107');
COMMIT;
GO
