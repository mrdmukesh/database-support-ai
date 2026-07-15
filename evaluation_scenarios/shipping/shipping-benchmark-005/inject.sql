SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[shipment_milestones](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0005-A',N'Failed',N'duplicate transaction',N'EVAL-SHIPPING-105');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0005-A',N'Failed',N'duplicate transaction evidence',N'EVAL-SHIPPING-105');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0005-A',N'Open',N'Primary synthetic defect: duplicate transaction',N'EVAL-SHIPPING-105');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0005-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-105');
COMMIT;
GO
