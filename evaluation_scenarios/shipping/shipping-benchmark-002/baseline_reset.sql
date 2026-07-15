SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-102';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-102';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-102';
DELETE FROM eval.[bookings] WHERE BusinessKey LIKE N'SHP-2026-0002%';
INSERT eval.[bookings](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0002-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-102');
COMMIT;
GO
