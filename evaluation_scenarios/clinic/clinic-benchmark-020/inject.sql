SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[lab_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0020-A',N'Failed',N'multi table investigation',N'EVAL-CLINIC-120');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0020-A',N'Failed',N'multi table investigation evidence',N'EVAL-CLINIC-120');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0020-A',N'Open',N'Primary synthetic defect: multi table investigation',N'EVAL-CLINIC-120');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0020-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-120');
COMMIT;
GO
