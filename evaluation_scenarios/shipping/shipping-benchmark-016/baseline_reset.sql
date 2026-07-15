SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-116';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-116';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-116';
DELETE FROM eval.[bills_of_lading] WHERE BusinessKey LIKE N'SHP-2026-0016%';
INSERT eval.[bills_of_lading](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0016-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-116');
COMMIT;
GO
