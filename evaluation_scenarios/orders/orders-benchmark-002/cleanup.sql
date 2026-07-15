SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-102';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-102';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-102';
DELETE FROM eval.[sales_order_lines] WHERE BusinessKey LIKE N'ORD-2026-0002%';
COMMIT;
GO
