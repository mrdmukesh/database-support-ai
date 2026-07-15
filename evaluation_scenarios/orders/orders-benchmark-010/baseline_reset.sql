SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-110';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-110';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-110';
DELETE FROM eval.[sales_order_lines] WHERE BusinessKey LIKE N'ORD-2026-0010%';
INSERT eval.[sales_order_lines](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0010-A',N'Ready',N'Clean benchmark baseline',N'EVAL-ORDERS-110');
COMMIT;
GO
