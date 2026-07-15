SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[encounters](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0010-A',N'Failed',N'retry failure',N'EVAL-CLINIC-110');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0010-A',N'Failed',N'retry failure evidence',N'EVAL-CLINIC-110');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0010-A',N'Open',N'Primary synthetic defect: retry failure',N'EVAL-CLINIC-110');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0010-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-110');
COMMIT;
GO
