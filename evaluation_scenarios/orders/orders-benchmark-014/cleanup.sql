SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-114';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-114';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-114';
DELETE FROM eval.[inventory_movements] WHERE BusinessKey LIKE N'ORD-2026-0014%';
COMMIT;
GO
