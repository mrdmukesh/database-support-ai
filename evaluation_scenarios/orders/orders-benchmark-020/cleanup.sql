SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-120';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-120';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-120';
DELETE FROM eval.[pick_tasks] WHERE BusinessKey LIKE N'ORD-2026-0020%';
COMMIT;
GO
