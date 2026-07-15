SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.[integration_messages] WHERE CorrelationId=N'EVAL-SHIPPING-115';
DELETE FROM eval.[exceptions] WHERE CorrelationId=N'EVAL-SHIPPING-115';
DELETE FROM eval.[audit_history] WHERE CorrelationId=N'EVAL-SHIPPING-115';
DELETE FROM eval.[voyages] WHERE BusinessKey LIKE N'SHP-2026-0015%';
INSERT eval.[voyages](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0015-A',N'Ready',N'Clean benchmark baseline',N'EVAL-SHIPPING-115');
COMMIT;
GO
