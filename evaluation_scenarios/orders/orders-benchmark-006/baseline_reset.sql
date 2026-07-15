SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-106';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-106';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-106';
DELETE FROM eval.[inventory_movements] WHERE BusinessKey LIKE N'ORD-2026-0006%';
INSERT eval.[inventory_movements](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0006-A',N'Ready',N'Clean benchmark baseline',N'EVAL-ORDERS-106');
COMMIT;
GO
