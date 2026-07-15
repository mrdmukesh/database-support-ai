SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-114';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-114';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-114';
DELETE FROM eval.[transport_work_orders] WHERE BusinessKey LIKE N'SHP-2026-0014%';
COMMIT;
GO
