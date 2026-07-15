SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[procedures_performed](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0008-A',N'Failed',N'integration failure',N'EVAL-CLINIC-108');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0008-A',N'Failed',N'integration failure evidence',N'EVAL-CLINIC-108');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0008-A',N'Open',N'Primary synthetic defect: integration failure',N'EVAL-CLINIC-108');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0008-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-108');
COMMIT;
GO
