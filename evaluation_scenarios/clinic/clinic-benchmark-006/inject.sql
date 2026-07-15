SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[prescriptions](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0006-A',N'Failed',N'workflow interruption',N'EVAL-CLINIC-106');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0006-A',N'Failed',N'workflow interruption evidence',N'EVAL-CLINIC-106');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0006-A',N'Open',N'Primary synthetic defect: workflow interruption',N'EVAL-CLINIC-106');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0006-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-106');
COMMIT;
GO
