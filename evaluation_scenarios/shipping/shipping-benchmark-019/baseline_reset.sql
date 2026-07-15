SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-119';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-119';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-119';
DELETE FROM eval.[container_assignments] WHERE BusinessKey LIKE N'SHP-2026-0019%';
INSERT eval.[container_assignments](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0019-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-119');
COMMIT;
GO
