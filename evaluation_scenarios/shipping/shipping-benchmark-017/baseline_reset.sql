SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-117';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-117';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-117';
DELETE FROM eval.[shipments] WHERE BusinessKey LIKE N'SHP-2026-0017%';
INSERT eval.[shipments](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0017-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-117');
COMMIT;
GO
