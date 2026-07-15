SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-113';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-113';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-113';
DELETE FROM eval.[shipment_milestones] WHERE BusinessKey LIKE N'SHP-2026-0013%';
INSERT eval.[shipment_milestones](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0013-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-113');
COMMIT;
GO
