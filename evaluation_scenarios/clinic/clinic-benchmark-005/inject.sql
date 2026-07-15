SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[lab_results](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0005-A',N'Failed',N'duplicate transaction',N'EVAL-CLINIC-105');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0005-A',N'Failed',N'duplicate transaction evidence',N'EVAL-CLINIC-105');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0005-A',N'Open',N'Primary synthetic defect: duplicate transaction',N'EVAL-CLINIC-105');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0005-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-105');
COMMIT;
GO
