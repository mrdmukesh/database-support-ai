SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-ORDERS-115';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-ORDERS-115';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-ORDERS-115';
DELETE FROM eval.[receipts] WHERE BusinessKey LIKE N'ORD-2026-0015%';
INSERT eval.[receipts](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0015-A',N'Ready',N'Clean benchmark baseline',N'EVAL-ORDERS-115');
COMMIT;
GO
