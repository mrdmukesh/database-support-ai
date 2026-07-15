SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[appointments](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0001-A',N'Failed',N'exact entity lookup',N'EVAL-CLINIC-101');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0001-A',N'Failed',N'exact entity lookup evidence',N'EVAL-CLINIC-101');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0001-A',N'Open',N'Primary synthetic defect: exact entity lookup',N'EVAL-CLINIC-101');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0001-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-101');
COMMIT;
GO
