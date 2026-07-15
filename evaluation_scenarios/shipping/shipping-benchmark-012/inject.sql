SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[container_events](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0012-A',N'Failed',N'missing reference data',N'EVAL-SHIPPING-112');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0012-A',N'Failed',N'missing reference data evidence',N'EVAL-SHIPPING-112');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0012-A',N'Open',N'Primary synthetic defect: missing reference data',N'EVAL-SHIPPING-112');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0012-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-112');
COMMIT;
GO
