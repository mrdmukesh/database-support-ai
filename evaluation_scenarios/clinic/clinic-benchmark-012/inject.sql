SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[lab_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0012-A',N'Failed',N'missing reference data',N'EVAL-CLINIC-112');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0012-A',N'Failed',N'missing reference data evidence',N'EVAL-CLINIC-112');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0012-A',N'Open',N'Primary synthetic defect: missing reference data',N'EVAL-CLINIC-112');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0012-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-112');
COMMIT;
GO
