SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[appointments](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0009-A',N'Failed',N'queue backlog',N'EVAL-CLINIC-109');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0009-A',N'Failed',N'queue backlog evidence',N'EVAL-CLINIC-109');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0009-A',N'Open',N'Primary synthetic defect: queue backlog',N'EVAL-CLINIC-109');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0009-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-109');
COMMIT;
GO
