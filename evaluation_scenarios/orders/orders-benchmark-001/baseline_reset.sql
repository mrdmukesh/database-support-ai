SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-101';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-101';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-101';
DELETE FROM eval.[sales_orders] WHERE BusinessKey LIKE N'ORD-2026-0001%';
INSERT eval.[sales_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0001-A',N'Ready',N'Clean benchmark baseline',N'EVAL-ORDERS-101');
COMMIT;
GO
