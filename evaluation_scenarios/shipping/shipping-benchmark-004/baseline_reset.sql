SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-104';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-104';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-104';
DELETE FROM eval.[container_events] WHERE BusinessKey LIKE N'SHP-2026-0004%';
INSERT eval.[container_events](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0004-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-104');
COMMIT;
GO
