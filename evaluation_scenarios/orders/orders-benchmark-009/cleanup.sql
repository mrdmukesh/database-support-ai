SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-109';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-109';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-109';
DELETE FROM eval.[sales_orders] WHERE BusinessKey LIKE N'ORD-2026-0009%';
COMMIT;
GO
