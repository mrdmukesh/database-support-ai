SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[claims](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0019-A',N'Failed',N'incorrect business status',N'EVAL-CLINIC-119');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0019-A',N'Failed',N'incorrect business status evidence',N'EVAL-CLINIC-119');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0019-A',N'Open',N'Primary synthetic defect: incorrect business status',N'EVAL-CLINIC-119');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0019-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-119');
COMMIT;
GO
