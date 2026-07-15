SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-105';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-105';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-105';
DELETE FROM eval.[shipments] WHERE BusinessKey LIKE N'ORD-2026-0005%';
INSERT eval.[shipments](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0005-A',N'Ready',N'Clean benchmark baseline',N'EVAL-ORDERS-105');
COMMIT;
GO
