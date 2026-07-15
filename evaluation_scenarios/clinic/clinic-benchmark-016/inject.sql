SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[procedures_performed](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0016-A',N'Failed',N'concurrency race condition',N'EVAL-CLINIC-116');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0016-A',N'Failed',N'concurrency race condition evidence',N'EVAL-CLINIC-116');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0016-A',N'Open',N'Primary synthetic defect: concurrency race condition',N'EVAL-CLINIC-116');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0016-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-116');
COMMIT;
GO
