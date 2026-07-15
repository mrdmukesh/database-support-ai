SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-111';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-111';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-111';
DELETE FROM eval.[allocations] WHERE BusinessKey LIKE N'ORD-2026-0011%';
INSERT eval.[allocations](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0011-A',N'Ready',N'Clean benchmark baseline',N'EVAL-ORDERS-111');
COMMIT;
GO
