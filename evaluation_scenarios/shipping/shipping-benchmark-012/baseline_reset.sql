SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-112';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-112';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-112';
DELETE FROM eval.[container_events] WHERE BusinessKey LIKE N'SHP-2026-0012%';
INSERT eval.[container_events](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0012-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-112');
COMMIT;
GO
