SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-111';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-111';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-111';
DELETE FROM eval.[container_assignments] WHERE BusinessKey LIKE N'SHP-2026-0011%';
INSERT eval.[container_assignments](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0011-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-111');
COMMIT;
GO
