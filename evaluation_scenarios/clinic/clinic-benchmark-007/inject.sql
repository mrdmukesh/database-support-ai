SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payments](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0007-A',N'Failed',N'exception handling',N'EVAL-CLINIC-107');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0007-A',N'Failed',N'exception handling evidence',N'EVAL-CLINIC-107');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0007-A',N'Open',N'Primary synthetic defect: exception handling',N'EVAL-CLINIC-107');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0007-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-107');
COMMIT;
GO
