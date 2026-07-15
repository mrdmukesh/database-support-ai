SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-107';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-107';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-107';
DELETE FROM eval.[voyages] WHERE BusinessKey LIKE N'SHP-2026-0007%';
INSERT eval.[voyages](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0007-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-107');
COMMIT;
GO
