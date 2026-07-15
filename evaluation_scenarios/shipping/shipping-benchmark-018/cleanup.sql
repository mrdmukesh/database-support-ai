SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-118';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-118';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-118';
DELETE FROM eval.[bookings] WHERE BusinessKey LIKE N'SHP-2026-0018%';
COMMIT;
GO
