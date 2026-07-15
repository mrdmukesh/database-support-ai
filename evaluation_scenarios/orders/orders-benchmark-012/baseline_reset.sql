SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-112';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-112';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-112';
DELETE FROM eval.[pick_tasks] WHERE BusinessKey LIKE N'ORD-2026-0012%';
INSERT eval.[pick_tasks](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0012-A',N'Ready',N'Clean benchmark baseline',N'EVAL-ORDERS-112');
COMMIT;
GO
