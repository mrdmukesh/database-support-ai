SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-CLINIC-114';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-CLINIC-114';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-CLINIC-114';
DELETE FROM eval.[prescriptions] WHERE BusinessKey LIKE N'CLN-2026-0014%';
INSERT eval.[prescriptions](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0014-A',N'Ready',N'Clean benchmark baseline',N'EVAL-CLINIC-114');
COMMIT;
GO
